"""Thin async client for the Zalo Bot API.

Knows nothing about MCP. Four calls: getUpdates, sendMessage, getMe,
getWebhookInfo.

Zalo puts the bot token in the URL path (``/bot<TOKEN>/getUpdates``), so any
error message or log line that includes a URL leaks the token. Every string
this module raises or logs goes through ``_redact()`` first, and exceptions
are raised ``from None`` so the original httpx exception (whose message
contains the full URL) never appears in tracebacks.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://bot-api.zapps.me"
MAX_MESSAGE_LEN = 2000
TEXT_EVENT = "message.text.received"


class ZaloApiError(Exception):
    """Base for Zalo API failures. Messages are always token-redacted."""


class ZaloClientError(ZaloApiError):
    """Our request was wrong (4xx or ok=false). Do not retry."""


class ZaloTransientError(ZaloApiError):
    """Server-side or network trouble (5xx, 429, timeouts). Caller may back off and retry."""


@dataclass(frozen=True)
class InboundMessage:
    user_id: str
    display_name: str
    is_bot: bool
    chat_id: str
    chat_type: str  # "PRIVATE" | "GROUP"
    text: str
    message_id: str
    date: int


def parse_update(result: Any) -> InboundMessage | None:
    """Extract an InboundMessage from a getUpdates result entry.

    Returns None for non-text events or payloads that don't match the
    documented shape (Zalo only documents message.text.received; other event
    shapes are unknown until measured against a real bot).
    """
    if not isinstance(result, dict) or result.get("event_name") != TEXT_EVENT:
        return None
    message = result.get("message")
    if not isinstance(message, dict):
        return None
    sender = message.get("from")
    chat = message.get("chat")
    if not isinstance(sender, dict) or not isinstance(chat, dict):
        return None
    try:
        return InboundMessage(
            user_id=str(sender["id"]),
            display_name=str(sender.get("display_name", "")),
            is_bot=bool(sender.get("is_bot", False)),
            chat_id=str(chat["id"]),
            chat_type=str(chat.get("chat_type", "PRIVATE")),
            text=str(message["text"]),
            message_id=str(message["message_id"]),
            date=int(message.get("date", 0)),
        )
    except (KeyError, TypeError, ValueError):
        return None


def split_message(text: str, limit: int = MAX_MESSAGE_LEN) -> list[str]:
    """Split text into <=limit pieces, preferring paragraph, then line, then
    word boundaries. Hard cut only when a single unbroken run exceeds limit."""
    if not text:
        return []
    out: list[str] = []
    rest = text
    while len(rest) > limit:
        para = rest.rfind("\n\n", 0, limit)
        line = rest.rfind("\n", 0, limit)
        space = rest.rfind(" ", 0, limit)
        if para > limit // 2:
            cut = para
        elif line > limit // 2:
            cut = line
        elif space > 0:
            cut = space
        else:
            cut = limit
        out.append(rest[:cut])
        rest = rest[cut:].lstrip("\n ")
    if rest:
        out.append(rest)
    return out


class _TokenRedactingFilter(logging.Filter):
    """Scrub the bot token out of third-party log records. httpx logs the
    full request URL at INFO ("HTTP Request: POST .../bot<TOKEN>/getMe"), so
    filtering our own log lines is not enough."""

    def __init__(self, token: str) -> None:
        super().__init__()
        self._token = token

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        if self._token in message:
            record.msg = message.replace(self._token, "<token>")
            record.args = ()
        return True


# Only third-party loggers. A logging.Filter attached to a logger runs for
# records logged *on that logger*, not for records propagating up from its
# children, so listing "zalo_bot_mcp" here would cover this module and quietly
# miss every submodule. This package therefore takes the other route: it never
# puts a URL in a log record at all (see _call, which logs the method name).
# test_module_never_logs_a_url enforces that.
#
# httpcore is deliberately absent for the same child-logger reason: it logs on
# httpcore.connection/http11/etc., which a filter on "httpcore" would never
# see. Verified against a live server at DEBUG: httpcore does not log URLs, so
# no filter is needed there.
_REDACTED_LOGGERS = ("httpx",)


class ZaloBotApi:
    def __init__(
        self,
        token: str,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        timeout: float = 10.0,
    ) -> None:
        if not token:
            raise ValueError("empty bot token")
        self._token = token
        self._log_filter = _TokenRedactingFilter(token)
        for name in _REDACTED_LOGGERS:
            logging.getLogger(name).addFilter(self._log_filter)
        self._client = httpx.AsyncClient(
            base_url=f"{BASE_URL}/bot{token}",
            transport=transport,
            timeout=timeout,
        )

    def __repr__(self) -> str:
        return "ZaloBotApi(token=<token>)"

    def _redact(self, text: str) -> str:
        return text.replace(self._token, "<token>")

    async def _call(
        self,
        method: str,
        payload: dict[str, Any],
        *,
        timeout: float | None = None,
        timeout_is_empty: bool = False,
    ) -> Any:
        """timeout_is_empty: a long poll that ends with no messages is NOT an
        error, Zalo answers it with HTTP 408 {"ok":false,"description":
        "Request timeout"} (measured against a real bot). With this flag the
        408 becomes a normal None result; without it 408 stays a client
        error. Checked at both layers because the ok:false branch would
        otherwise swallow it."""
        logger.debug("calling %s", method)
        try:
            resp = await self._client.post(f"/{method}", json=payload, timeout=timeout)
        except httpx.HTTPError as exc:
            # from None: the httpx exception message contains the full URL
            # (token included) and must not surface in tracebacks.
            raise ZaloTransientError(self._redact(f"{method}: {exc}")) from None
        if timeout_is_empty and resp.status_code == 408:
            return None
        if resp.status_code == 429 or resp.status_code >= 500:
            raise ZaloTransientError(
                self._redact(f"{method}: HTTP {resp.status_code}: {resp.text[:200]}")
            )
        if resp.status_code >= 400:
            raise ZaloClientError(
                self._redact(f"{method}: HTTP {resp.status_code}: {resp.text[:200]}")
            )
        try:
            data = resp.json()
        except ValueError:
            raise ZaloTransientError(
                self._redact(f"{method}: non-JSON response: {resp.text[:200]}")
            ) from None
        if (
            timeout_is_empty
            and isinstance(data, dict)
            and not data.get("ok")
            and "timeout" in str(data.get("description", "")).lower()
        ):
            return None
        if not isinstance(data, dict) or not data.get("ok"):
            raise ZaloClientError(self._redact(f"{method}: API error: {data!r}"[:500]))
        return data.get("result")

    async def get_updates(self, timeout: int = 30) -> Any:
        """Long poll for updates. Returns None when the window closed with no
        messages, the NORMAL idle path, not an error."""
        # HTTP read timeout must outlast the long poll itself.
        return await self._call(
            "getUpdates", {"timeout": timeout}, timeout=timeout + 10, timeout_is_empty=True
        )

    async def send_message(
        self, chat_id: str, text: str, parse_mode: str | None = None
    ) -> Any:
        if not 1 <= len(text) <= MAX_MESSAGE_LEN:
            raise ValueError(
                f"text length {len(text)} outside 1..{MAX_MESSAGE_LEN}; use split_message()"
            )
        payload: dict[str, Any] = {"chat_id": chat_id, "text": text}
        if parse_mode is not None:
            payload["parse_mode"] = parse_mode
        return await self._call("sendMessage", payload)

    async def get_me(self) -> Any:
        return await self._call("getMe", {})

    async def get_webhook_info(self) -> Any:
        """Returns the webhook info dict when a webhook is set, or None when
        none exists. A clean bot answers with HTTP 404 {"ok":false,
        "description":"Not Found"} (measured, not documented), so any
        client-class error here simply means "no webhook"."""
        try:
            return await self._call("getWebhookInfo", {})
        except ZaloClientError:
            return None

    async def aclose(self) -> None:
        await self._client.aclose()
        for name in _REDACTED_LOGGERS:
            logging.getLogger(name).removeFilter(self._log_filter)

    async def __aenter__(self) -> ZaloBotApi:  # noqa: PYI034, 3.10 has no typing.Self
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()
