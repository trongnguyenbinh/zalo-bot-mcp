"""channel.py tests — reply chat_id enforcement (the anti-exfiltration
check), splitting, and the buffer-until-attached path. No real network."""

import json
from types import SimpleNamespace

import httpx
import pytest

from zalo_bot_mcp.channel import CHANNEL_METHOD, ZaloChannel
from zalo_bot_mcp.zalo_api import InboundMessage, ZaloBotApi

TOKEN = "test-token"


class FakeOutbound:
    def __init__(self):
        self.sent = []

    async def notify(self, method, params):
        self.sent.append((method, params))


def fake_ctx(outbound):
    connection = SimpleNamespace(outbound=outbound)
    return SimpleNamespace(session=SimpleNamespace(_connection=connection))


def make_channel(sent_bodies):
    def handler(request):
        sent_bodies.append(json.loads(request.content))
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
    assert sent == [{"chat_id": "c1", "text": "hello back"}]


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


async def test_status_counts_and_known_chats():
    channel = make_channel([])
    outbound = FakeOutbound()
    await channel.capture_outbound(fake_ctx(outbound))
    await channel.push_inbound(msg(chat="c1", message_id="m1"))
    await channel.push_inbound(msg(chat="c2", message_id="m2"))
    status = channel.status()
    assert status["processed"] == 2
    assert status["known_chats"] == ["c1", "c2"]
