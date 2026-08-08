"""channel.py tests — reply chat_id enforcement (the anti-exfiltration
check), splitting, and the buffer-until-attached path. No real network."""

import json
from types import SimpleNamespace

import httpx
import pytest

from zalo_bot_mcp.channel import CHANNEL_METHOD, ZaloChannel
from zalo_bot_mcp.zalo_api import InboundMessage, ZaloBotApi, ZaloTransientError

TOKEN = "test-token"


class FakeOutbound:
    def __init__(self):
        self.sent = []

    async def notify(self, method, params):
        self.sent.append((method, params))


def fake_ctx(outbound):
    connection = SimpleNamespace(outbound=outbound)
    return SimpleNamespace(session=SimpleNamespace(_connection=connection))


def make_channel(sent_bodies, actions=None, reject_markdown=False, action_status=200):
    """sent_bodies collects sendMessage payloads only; sendChatAction payloads
    go to `actions` (dropped when None) so message-centric assertions don't
    see the typing indicator. reject_markdown=True answers any markdown
    sendMessage with HTTP 400, the shape a formatting rejection would take."""

    def handler(request):
        body = json.loads(request.content)
        if request.url.path.endswith("/sendChatAction"):
            if actions is not None:
                actions.append(body)
            return httpx.Response(action_status, json={"ok": action_status == 200})
        if reject_markdown and body.get("parse_mode") == "markdown":
            return httpx.Response(400, json={"ok": False, "description": "Bad Request"})
        sent_bodies.append(body)
        return httpx.Response(200, json={"ok": True, "result": {}})

    api = ZaloBotApi(TOKEN, transport=httpx.MockTransport(handler))
    return ZaloChannel(api)


def msg(user="u1", chat="c1", chat_type="PRIVATE", text="hi", message_id="m1"):
    return InboundMessage(
        user_id=user,
        display_name="Someone",
        is_bot=False,
        chat_id=chat,
        chat_type=chat_type,
        text=text,
        message_id=message_id,
        date=1750316131602,
    )


# --- reply chat_id enforcement ----------------------------------------------


async def test_reply_refuses_chat_that_never_came_through_gate():
    sent = []
    channel = make_channel(sent)
    with pytest.raises(ValueError, match="never messaged"):
        await channel.reply("attacker-chat", "leaked data")
    assert sent == []


async def test_reply_works_for_chat_registered_by_push_inbound():
    sent = []
    channel = make_channel(sent)
    await channel.push_inbound(msg(chat="c1"))
    note = await channel.reply("c1", "hello back")
    assert "1 message" in note
    assert sent == [{"chat_id": "c1", "text": "hello back", "parse_mode": "markdown"}]


async def test_reply_still_refuses_other_chats_after_one_is_known():
    sent = []
    channel = make_channel(sent)
    await channel.push_inbound(msg(chat="c1"))
    with pytest.raises(ValueError):
        await channel.reply("c2", "hi")
    assert sent == []


async def test_reply_rejects_empty_text():
    sent = []
    channel = make_channel(sent)
    await channel.push_inbound(msg(chat="c1"))
    with pytest.raises(ValueError, match="empty"):
        await channel.reply("c1", "")
    assert sent == []


# --- splitting ---------------------------------------------------------------


async def test_reply_splits_long_text_into_sequential_sends():
    sent = []
    channel = make_channel(sent)
    await channel.push_inbound(msg(chat="c1"))
    long_text = "\n".join(f"line {i} " + "x" * 80 for i in range(60))
    assert len(long_text) > 4000
    note = await channel.reply("c1", long_text)
    assert len(sent) >= 3
    assert all(1 <= len(body["text"]) <= 2000 for body in sent)
    assert all(body["chat_id"] == "c1" for body in sent)
    assert f"{len(sent)} message" in note


# --- notification push and buffering ----------------------------------------


async def test_push_delivers_notification_with_meta():
    channel = make_channel([])
    outbound = FakeOutbound()
    await channel.capture_outbound(fake_ctx(outbound))
    await channel.push_inbound(msg(user="u9", chat="c9", text="xin chao", message_id="m9"))
    assert len(outbound.sent) == 1
    method, params = outbound.sent[0]
    assert method == CHANNEL_METHOD
    assert params["content"] == "xin chao"
    meta = params["meta"]
    assert meta["chat_id"] == "c9"
    assert meta["message_id"] == "m9"
    assert meta["user"] == "Someone"
    assert meta["user_id"] == "u9"
    assert meta["ts"].startswith("2025-06-")  # 1750316131602 ms epoch


async def test_push_buffers_until_session_attaches_then_flushes_in_order():
    channel = make_channel([])
    await channel.push_inbound(msg(message_id="m1", text="first"))
    await channel.push_inbound(msg(message_id="m2", text="second"))
    assert channel.status()["buffered"] == 2

    outbound = FakeOutbound()
    await channel.capture_outbound(fake_ctx(outbound))
    assert [p["content"] for _, p in outbound.sent] == ["first", "second"]
    assert channel.status()["buffered"] == 0


# --- markdown and the plain-text fallback ------------------------------------


async def test_reply_falls_back_to_plain_when_markdown_rejected():
    """The message must never be lost: a 400 on the markdown send means the
    same text goes out again without parse_mode."""
    sent = []
    channel = make_channel(sent, reject_markdown=True)
    await channel.push_inbound(msg(chat="c1"))
    note = await channel.reply("c1", "has **markup** that zalo hates")
    assert "1 message" in note
    assert sent == [{"chat_id": "c1", "text": "has **markup** that zalo hates"}]
    assert "parse_mode" not in sent[0]


async def test_reply_fallback_covers_every_piece_of_a_split_reply():
    sent = []
    channel = make_channel(sent, reject_markdown=True)
    await channel.push_inbound(msg(chat="c1"))
    long_text = "\n".join(f"line {i} " + "x" * 80 for i in range(60))
    await channel.reply("c1", long_text)
    assert len(sent) >= 3
    assert all("parse_mode" not in body for body in sent)
    assert "".join(b["text"] for b in sent).startswith("line 0")


async def test_reply_transient_error_still_raises():
    """Only formatting rejections fall back; a 500 would fail in plain text
    too, so it propagates for the caller's backoff."""

    def handler(request):
        return httpx.Response(500, text="boom")

    api = ZaloBotApi(TOKEN, transport=httpx.MockTransport(handler))
    channel = ZaloChannel(api)
    channel._known_chats.add("c1")
    with pytest.raises(ZaloTransientError):
        await channel.reply("c1", "hi")


async def test_reply_converts_code_fences_before_sending():
    """reply() runs to_zalo_markdown: no triple-backtick fence may reach the
    wire, and code with *args must go out wrapped in single backticks."""
    sent = []
    channel = make_channel(sent)
    await channel.push_inbound(msg(chat="c1"))
    await channel.reply("c1", "Kết quả **tốt**:\n```python\nrun(*args)\n```")
    assert len(sent) == 1
    body = sent[0]["text"]
    assert "```" not in body
    assert "`run(*args)`" in body
    assert "**tốt**" in body


# --- typing indicator ---------------------------------------------------------


async def test_push_inbound_sends_typing_before_the_notification():
    events = []

    class RecordingOutbound:
        async def notify(self, method, params):
            events.append(("notify", params["meta"]["chat_id"]))

    def handler(request):
        body = json.loads(request.content)
        if request.url.path.endswith("/sendChatAction"):
            events.append(("action", body))
            return httpx.Response(200, json={"ok": True})
        return httpx.Response(200, json={"ok": True, "result": {}})

    api = ZaloBotApi(TOKEN, transport=httpx.MockTransport(handler))
    channel = ZaloChannel(api)
    await channel.capture_outbound(fake_ctx(RecordingOutbound()))
    await channel.push_inbound(msg(chat="c7"))
    assert events == [
        ("action", {"chat_id": "c7", "action": "typing"}),
        ("notify", "c7"),
    ]


@pytest.mark.parametrize("action_status", [400, 500])
async def test_push_inbound_survives_typing_failure(action_status):
    """typing is decoration; the notification must go out even when
    sendChatAction fails either way (client or server error)."""
    channel = make_channel([], action_status=action_status)
    outbound = FakeOutbound()
    await channel.capture_outbound(fake_ctx(outbound))
    await channel.push_inbound(msg(chat="c1", text="still delivered"))
    assert [p["content"] for _, p in outbound.sent] == ["still delivered"]


async def test_status_counts_and_known_chats():
    channel = make_channel([])
    outbound = FakeOutbound()
    await channel.capture_outbound(fake_ctx(outbound))
    await channel.push_inbound(msg(chat="c1", message_id="m1"))
    await channel.push_inbound(msg(chat="c2", message_id="m2"))
    status = channel.status()
    assert status["processed"] == 2
    assert status["known_chats"] == ["c1", "c2"]


def test_instructions_list_the_real_skill_names():
    """The model was inventing /zalo-allow because nothing told it the real
    names. Every skill on disk must appear, spelled with the colon."""
    from pathlib import Path

    from zalo_bot_mcp.channel import INSTRUCTIONS

    skills = sorted(p.name for p in (Path(__file__).parent.parent / "skills").iterdir() if p.is_dir())
    assert skills, "no skills found; this test would pass vacuously"
    for name in skills:
        assert f"/zalo:{name}" in INSTRUCTIONS, f"/zalo:{name} missing from INSTRUCTIONS"
    assert "/zalo-" not in INSTRUCTIONS, "hyphen form would teach the wrong name"
