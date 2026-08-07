"""main.py diagnostics tests: webhook detection at startup and in the poll
loop, empty-poll survival, hot-replay throttling, and error descriptions
surviving into the logs. MockTransport only; failure fixtures are verbatim
from a real bot."""

import logging

import httpx
import pytest

from zalo_bot_mcp.access import AccessStore
from zalo_bot_mcp.channel import ZaloChannel
from zalo_bot_mcp.main import (
    MIN_POLL_INTERVAL,
    _webhook_url,
    check_webhook_clear,
    handle_update,
    poll_loop,
)
from zalo_bot_mcp.state import SeenChats, SeenMessages
from zalo_bot_mcp.zalo_api import ZaloBotApi, ZaloClientError

TOKEN = "test-token"

WEBHOOK_400 = (
    '{"ok":false,"description":"You cannot use this API while a webhook is set.'
    ' Please remove the webhook first","error_code":400}'
)
EMPTY_POLL_408 = '{"ok":false,"description":"Request timeout","error_code":408}'
NO_WEBHOOK_404 = '{"ok":false,"description":"Not Found","error_code":404}'


def make_api(handler):
    return ZaloBotApi(TOKEN, transport=httpx.MockTransport(handler))


# --- _webhook_url ------------------------------------------------------------


def test_webhook_url_present():
    assert _webhook_url({"url": "https://n8n.example/hook", "updated_at": 1}) == (
        "https://n8n.example/hook"
    )


def test_webhook_url_tolerates_missing_empty_and_odd_shapes():
    assert _webhook_url({}) is None
    assert _webhook_url({"url": ""}) is None
    assert _webhook_url({"url": "   "}) is None
    assert _webhook_url({"url": None}) is None
    assert _webhook_url(None) is None
    assert _webhook_url([]) is None
    assert _webhook_url("https://not-a-dict") is None


# --- check_webhook_clear at startup ------------------------------------------


async def test_startup_dies_with_url_when_webhook_set(caplog):
    def handler(request):
        assert request.url.path.endswith("/getWebhookInfo")
        return httpx.Response(
            200, json={"ok": True, "result": {"url": "https://n8n.example/hook", "updated_at": 1}}
        )

    async with make_api(handler) as api:
        with pytest.raises(SystemExit), caplog.at_level("CRITICAL"):
            await check_webhook_clear(api)
    assert "https://n8n.example/hook" in caplog.text
    assert "WARNING" in caplog.text  # the "deleting it breaks things" warning


async def test_startup_clean_bot_404_passes_quietly(caplog):
    # A clean bot answers getWebhookInfo with 404 (measured). Startup must
    # proceed without even a warning — this is the normal path.
    async with make_api(lambda request: httpx.Response(404, text=NO_WEBHOOK_404)) as api:
        with caplog.at_level("WARNING"):
            await check_webhook_clear(api)  # must not raise
    assert "getWebhookInfo" not in caplog.text


async def test_startup_passes_when_result_empty():
    async with make_api(
        lambda request: httpx.Response(200, json={"ok": True, "result": {}})
    ) as api:
        await check_webhook_clear(api)  # must not raise


async def test_startup_tolerates_transient_getwebhookinfo_failure(caplog):
    async with make_api(lambda request: httpx.Response(503, text="upstream sad")) as api:
        with caplog.at_level("WARNING"):
            await check_webhook_clear(api)  # must not raise
    assert "continuing" in caplog.text


# --- poll loop diagnostics ---------------------------------------------------


def poll_fixtures(tmp_path, api):
    store = AccessStore(tmp_path / "access.json")
    seen = SeenMessages(tmp_path / "seen.json")
    chats = SeenChats(tmp_path / "seen-chats.json")
    return store, seen, chats, ZaloChannel(api)


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def fake_time(clock):
    """A sleep that advances the fake clock instead of really waiting."""

    async def _sleep(seconds):
        clock.t += seconds

    return _sleep


async def test_poll_loop_webhook_400_logs_guidance(tmp_path, caplog):
    async with make_api(lambda request: httpx.Response(400, text=WEBHOOK_400)) as api:
        store, seen, chats, channel = poll_fixtures(tmp_path, api)
        with pytest.raises(ZaloClientError), caplog.at_level("CRITICAL"):
            await poll_loop(api, store, seen, chats, channel)
    assert "webhook" in caplog.text.lower()
    assert "separate bot" in caplog.text


async def test_poll_loop_survives_repeated_empty_polls(tmp_path):
    """The most common long-polling path: nobody writes for a while. Zalo
    answers each idle window with HTTP 408 — the poller must treat that as
    'no messages' and keep polling, not die on the first quiet 30 seconds
    (the bug this test exists to catch).

    Three empty polls, then a client error to break the loop. With the bug,
    the 408 itself raises and the count stops at 1; fixed, the poller lives
    through all three empty windows and only stops at call 4."""
    calls = {"n": 0}

    def handler(request):
        calls["n"] += 1
        if calls["n"] <= 3:
            return httpx.Response(408, text=EMPTY_POLL_408)
        return httpx.Response(400, text='{"ok":false,"description":"stop the test"}')

    clock = FakeClock()
    async with make_api(handler) as api:
        store, seen, chats, channel = poll_fixtures(tmp_path, api)
        with pytest.raises(ZaloClientError):
            await poll_loop(api, store, seen, chats, channel, clock=clock, sleep=fake_time(clock))
    assert calls["n"] == 4


REPLAYED_UPDATE = {
    "event_name": "message.text.received",
    "message": {
        "from": {"id": "user-1", "display_name": "Ed", "is_bot": False},
        "chat": {"id": "chat-1", "chat_type": "PRIVATE"},
        "text": "hello",
        "message_id": "m-replayed",
        "date": 1750316131602,
    },
}


async def test_poll_loop_floors_hot_replays(tmp_path, caplog):
    """Measured against the real API: once the queue is non-empty, Zalo
    answers getUpdates INSTANTLY and replays the same consumed update on
    every poll (no ack, no offset — nothing to advance). Before the floor
    existed this spun at ~12 req/s. N hot polls must now consume at least
    N * MIN_POLL_INTERVAL of (injected) time."""
    calls = {"updates": 0}

    def handler(request):
        if request.url.path.endswith("/getUpdates"):
            calls["updates"] += 1
            if calls["updates"] > 5:
                return httpx.Response(400, text='{"ok":false,"description":"stop the test"}')
            # Same already-known update, returned immediately, every time.
            return httpx.Response(200, json={"ok": True, "result": REPLAYED_UPDATE})
        # The pairing reply the first (non-duplicate) pass sends out.
        return httpx.Response(200, json={"ok": True, "result": {}})

    clock = FakeClock()
    async with make_api(handler) as api:
        store, seen, chats, channel = poll_fixtures(tmp_path, api)
        with (
            pytest.raises(ZaloClientError),
            caplog.at_level(logging.DEBUG, logger="zalo_bot_mcp.main"),
        ):
            await poll_loop(api, store, seen, chats, channel, clock=clock, sleep=fake_time(clock))

    assert calls["updates"] == 6
    # Five completed polls → at least five floor-lengths of time must have passed.
    assert clock.t >= 5 * MIN_POLL_INTERVAL
    # And the duplicate skips are visible in the logs for the next debugging session.
    assert "already-seen" in caplog.text


async def test_gate_drop_records_chat_for_pending_chats(tmp_path):
    """A blocked group must leave its chat_id in seen-chats.json; stderr is
    invisible under an MCP client, so this file is the operator's only way
    to find the chat_id for group-add."""
    group_update = {
        "event_name": "message.text.received",
        "message": {
            "from": {"id": "u-9", "display_name": "Ed", "is_bot": False},
            "chat": {"id": "g-new", "chat_type": "GROUP"},
            "text": "@bot hello",
            "message_id": "m-g1",
            "date": 1750316131602,
        },
    }
    async with make_api(lambda request: httpx.Response(200, json={"ok": True})) as api:
        store, seen, chats, channel = poll_fixtures(tmp_path, api)
        await handle_update(
            group_update, api=api, store=store, seen=seen, chats=chats, channel=channel
        )
    entry = chats.load()["g-new"]
    assert entry["chat_type"] == "GROUP"
    assert entry["user"] == "Ed"
    assert entry["user_id"] == "u-9"
    assert entry["count"] == 1


async def test_poll_loop_other_400_logs_the_actual_description(tmp_path, caplog):
    async with make_api(
        lambda request: httpx.Response(400, text="some very specific reason")
    ) as api:
        store, seen, chats, channel = poll_fixtures(tmp_path, api)
        with pytest.raises(ZaloClientError), caplog.at_level("CRITICAL"):
            await poll_loop(api, store, seen, chats, channel)
    # The description must survive into the log verbatim, not be swallowed.
    assert "some very specific reason" in caplog.text
