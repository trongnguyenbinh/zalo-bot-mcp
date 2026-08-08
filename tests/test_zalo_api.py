"""zalo_api tests. All network traffic is faked with httpx.MockTransport —
no real API calls, no real token."""

import json
import logging
import pathlib
import re

import httpx
import pytest

from zalo_bot_mcp import zalo_api
from zalo_bot_mcp.zalo_api import (
    InboundMessage,
    ZaloBotApi,
    ZaloClientError,
    ZaloTransientError,
    parse_update,
    split_message,
    to_zalo_markdown,
)

TOKEN = "1234567890:SECRET-token-do-not-log"

SAMPLE_RESULT = {
    "event_name": "message.text.received",
    "message": {
        "from": {"id": "user-1", "display_name": "Ed", "is_bot": False},
        "chat": {"id": "chat-1", "chat_type": "PRIVATE"},
        "text": "hello",
        "message_id": "m-1",
        "date": 1750316131602,
    },
}


def make_api(handler):
    return ZaloBotApi(TOKEN, transport=httpx.MockTransport(handler))


def ok_response(result):
    return httpx.Response(200, json={"ok": True, "result": result})


# --- request shape -----------------------------------------------------------


async def test_get_updates_url_and_body():
    seen = {}

    def handler(request):
        seen["path"] = request.url.path
        seen["body"] = json.loads(request.content)
        return ok_response(SAMPLE_RESULT)

    async with make_api(handler) as api:
        result = await api.get_updates()

    assert seen["path"] == f"/bot{TOKEN}/getUpdates"
    assert seen["body"] == {"timeout": 30}
    assert result == SAMPLE_RESULT


async def test_send_message_body_without_parse_mode():
    seen = {}

    def handler(request):
        seen["path"] = request.url.path
        seen["body"] = json.loads(request.content)
        return ok_response({"message_id": "m-2"})

    async with make_api(handler) as api:
        await api.send_message("chat-1", "hi there")

    assert seen["path"] == f"/bot{TOKEN}/sendMessage"
    assert seen["body"] == {"chat_id": "chat-1", "text": "hi there"}


async def test_send_message_includes_parse_mode_when_set():
    seen = {}

    def handler(request):
        seen["body"] = json.loads(request.content)
        return ok_response({})

    async with make_api(handler) as api:
        await api.send_message("chat-1", "*bold*", parse_mode="markdown")

    assert seen["body"]["parse_mode"] == "markdown"


async def test_send_chat_action_path_and_body():
    seen = {}

    def handler(request):
        seen["path"] = request.url.path
        seen["body"] = json.loads(request.content)
        return httpx.Response(200, json={"ok": True})

    async with make_api(handler) as api:
        await api.send_chat_action("chat-1")

    assert seen["path"] == f"/bot{TOKEN}/sendChatAction"
    assert seen["body"] == {"chat_id": "chat-1", "action": "typing"}


# --- to_zalo_markdown --------------------------------------------------------


def test_code_block_stars_and_underscores_stay_literal():
    """The reason this converter exists: *args and __init__ inside a fence
    must not turn into italics/bold. Each code line gets inline-code wrapped,
    which the docs promise preserves content."""
    text = '```python\ndef greet(*args):\n    name = "__init__"\n```'
    out = to_zalo_markdown(text)
    assert "```" not in out
    assert "`def greet(*args):`" in out
    assert '`    name = "__init__"`' in out


def test_code_block_inside_bold_prose_keeps_both_sides():
    text = "Trước là **kết luận đậm**.\n\n```python\nx = a * b * c\n```\n\nSau là *nghiêng*."
    out = to_zalo_markdown(text)
    assert "**kết luận đậm**" in out
    assert "*nghiêng*" in out
    assert "```" not in out
    assert "`x = a * b * c`" in out


def test_code_line_containing_backtick_is_escaped_not_wrapped():
    out = to_zalo_markdown("```bash\necho `date` x_y\n```")
    assert "```" not in out
    assert "\\`" in out
    assert "x\\_y" in out
    assert not out.startswith("`echo")


def test_blank_code_lines_pass_through_bare():
    out = to_zalo_markdown("```\na = 1\n\nb = 2\n```")
    assert out == "`a = 1`\n\n`b = 2`"


def test_unclosed_fence_treats_rest_as_code():
    out = to_zalo_markdown("intro\n```\nx = *p\ny = 2")
    assert out == "intro\n`x = *p`\n`y = 2`"


def test_links_unwrap_to_text_and_url():
    out = to_zalo_markdown("Xem [tài liệu](https://bot.zapps.me/docs/) nhé")
    assert out == "Xem tài liệu (https://bot.zapps.me/docs/) nhé"


def test_link_inside_inline_code_is_left_alone():
    out = to_zalo_markdown("dùng `[a](b)` nguyên văn")
    assert out == "dùng `[a](b)` nguyên văn"


def test_heading_five_plus_demoted_to_four():
    assert to_zalo_markdown("##### Title") == "#### Title"
    assert to_zalo_markdown("###### Deep") == "#### Deep"
    assert to_zalo_markdown("#### Keep") == "#### Keep"


def test_plain_prose_untouched():
    text = "Chào **anh**, đây là *ghi chú* với `inline code` và ~~gạch~~."
    assert to_zalo_markdown(text) == text


async def test_get_me():
    def handler(request):
        assert request.url.path == f"/bot{TOKEN}/getMe"
        return ok_response({"id": "bot-1", "is_bot": True})

    async with make_api(handler) as api:
        me = await api.get_me()
    assert me["id"] == "bot-1"


async def test_get_webhook_info_when_set():
    # Verbatim shape from a real bot with a webhook attached.
    def handler(request):
        assert request.url.path == f"/bot{TOKEN}/getWebhookInfo"
        return httpx.Response(
            200,
            json={
                "ok": True,
                "result": {"url": "https://example.test/hook", "updated_at": 1785647889461},
                "error_code": 0,
            },
        )

    async with make_api(handler) as api:
        info = await api.get_webhook_info()
    assert info["url"] == "https://example.test/hook"


async def test_get_webhook_info_clean_bot_404_returns_none():
    # Verbatim response from a real bot with NO webhook: HTTP 404, not
    # ok:true-with-empty-url. Must mean "no webhook", not an error.
    def handler(request):
        return httpx.Response(
            404, json={"ok": False, "description": "Not Found", "error_code": 404}
        )

    async with make_api(handler) as api:
        assert await api.get_webhook_info() is None


# --- empty long poll (the normal idle path) ----------------------------------

EMPTY_POLL_BODY = {"ok": False, "description": "Request timeout", "error_code": 408}


async def test_get_updates_408_means_no_messages_not_an_error():
    # Verbatim response from a real bot when nobody wrote during the poll
    # window. This is long polling's most common path — it must NOT raise.
    async with make_api(lambda request: httpx.Response(408, json=EMPTY_POLL_BODY)) as api:
        assert await api.get_updates() is None


async def test_get_updates_ok_false_timeout_description_also_means_empty():
    # Second layer: same body arriving with HTTP 200 must not fall into the
    # ok:false → ZaloClientError branch.
    async with make_api(lambda request: httpx.Response(200, json=EMPTY_POLL_BODY)) as api:
        assert await api.get_updates() is None


async def test_408_on_other_calls_still_raises():
    # timeout_is_empty applies to getUpdates only; a 408 on sendMessage is
    # still a client error.
    async with make_api(lambda request: httpx.Response(408, json=EMPTY_POLL_BODY)) as api:
        with pytest.raises(ZaloClientError):
            await api.send_message("chat-1", "hi")


async def test_send_message_rejects_empty_and_too_long():
    async with make_api(lambda request: ok_response({})) as api:
        with pytest.raises(ValueError):
            await api.send_message("chat-1", "")
        with pytest.raises(ValueError):
            await api.send_message("chat-1", "x" * 2001)


# --- error classification ----------------------------------------------------


async def test_4xx_raises_client_error():
    async with make_api(lambda request: httpx.Response(400, text="bad request")) as api:
        with pytest.raises(ZaloClientError):
            await api.get_me()


async def test_5xx_raises_transient_error():
    async with make_api(lambda request: httpx.Response(502, text="bad gateway")) as api:
        with pytest.raises(ZaloTransientError):
            await api.get_me()


async def test_429_raises_transient_error():
    async with make_api(lambda request: httpx.Response(429, text="slow down")) as api:
        with pytest.raises(ZaloTransientError):
            await api.get_me()


async def test_ok_false_raises_client_error():
    async with make_api(
        lambda request: httpx.Response(200, json={"ok": False, "description": "nope"})
    ) as api:
        with pytest.raises(ZaloClientError):
            await api.get_me()


async def test_network_error_raises_transient_error():
    def handler(request):
        raise httpx.ConnectError(f"failed to reach {request.url}")

    async with make_api(handler) as api:
        with pytest.raises(ZaloTransientError):
            await api.get_me()


# --- token redaction ---------------------------------------------------------


async def test_token_never_in_errors_or_logs(caplog):
    """Zalo puts the token in the URL path; prove it cannot leak through any
    failure mode's message, traceback chain, or log output."""

    def net_fail(request):
        raise httpx.ConnectError(f"failed to reach {request.url}")

    failing_handlers = [
        lambda request: httpx.Response(400, text=f"bad request to {request.url}"),
        lambda request: httpx.Response(500, text=f"boom at {request.url}"),
        lambda request: httpx.Response(200, text="not json"),
        net_fail,
    ]
    with caplog.at_level(logging.DEBUG):
        for handler in failing_handlers:
            async with make_api(handler) as api:
                with pytest.raises((ZaloClientError, ZaloTransientError)) as excinfo:
                    await api.get_me()
            exc = excinfo.value
            assert TOKEN not in str(exc)
            # No chained httpx exception carrying the raw URL in tracebacks.
            assert exc.__cause__ is None
            assert exc.__suppress_context__ or exc.__context__ is None
    assert TOKEN not in caplog.text


async def test_repr_hides_token():
    async with make_api(lambda request: ok_response({})) as api:
        assert TOKEN not in repr(api)


def test_module_never_logs_a_url():
    """This package must not put a URL in a log record.

    The redaction filter only covers httpx and httpcore. A logging.Filter runs
    for records logged on the logger it is attached to, not for records
    propagating up from child loggers, so this package cannot protect its own
    submodules that way. The token sits in the URL path, so the rule is simply:
    never log a URL. This test reads the source and fails if a logging call
    ever mentions one.
    """
    source = pathlib.Path(zalo_api.__file__).read_text()
    logging_calls = re.findall(r"logger\.\w+\((.*?)\)", source, re.DOTALL)
    offenders = [
        call
        for call in logging_calls
        if re.search(r"url|base_url|https?://|_client\.|self\._token", call)
    ]
    assert not offenders, f"logging call mentions a URL or the token: {offenders}"


# --- split_message -----------------------------------------------------------


def test_split_short_text_untouched():
    assert split_message("hello", limit=20) == ["hello"]


def test_split_empty_returns_nothing():
    assert split_message("") == []


def test_split_prefers_line_boundary():
    text = "line one\nline two\nline three"
    pieces = split_message(text, limit=20)
    assert pieces == ["line one\nline two", "line three"]


def test_split_never_cuts_mid_word():
    text = "alpha beta gamma delta epsilon zeta"
    pieces = split_message(text, limit=12)
    for piece in pieces:
        assert len(piece) <= 12
    # Reassembling on single spaces restores the original words in order.
    assert " ".join(pieces).split() == text.split()


def test_split_hard_cuts_single_long_run():
    text = "a" * 45
    pieces = split_message(text, limit=20)
    assert pieces == ["a" * 20, "a" * 20, "a" * 5]


def test_split_all_pieces_within_limit_and_lossless_on_paragraphs():
    text = "\n\n".join(f"paragraph {i} " + "word " * 30 for i in range(10))
    pieces = split_message(text, limit=200)
    assert all(0 < len(p) <= 200 for p in pieces)
    assert "".join(pieces).split() == text.split()


# --- parse_update ------------------------------------------------------------


def test_parse_update_documented_payload():
    msg = parse_update(SAMPLE_RESULT)
    assert msg == InboundMessage(
        user_id="user-1",
        display_name="Ed",
        is_bot=False,
        chat_id="chat-1",
        chat_type="PRIVATE",
        text="hello",
        message_id="m-1",
        date=1750316131602,
    )


def test_parse_update_ignores_other_events():
    assert parse_update({"event_name": "message.image.received", "message": {}}) is None
    assert parse_update({"event_name": "message.text.received"}) is None
    assert parse_update(None) is None
    assert parse_update({}) is None


def test_parse_update_ignores_malformed_message():
    broken = {"event_name": "message.text.received", "message": {"from": {}, "chat": {}}}
    assert parse_update(broken) is None
