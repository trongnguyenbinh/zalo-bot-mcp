"""Wire everything together: the Zalo poller and the MCP stdio server run
side by side in one process.

stdout belongs to the MCP protocol, all human-facing output goes to stderr
via logging, and this process never sends alerts anywhere but Zalo itself.
"""

from __future__ import annotations

import asyncio
import logging
import signal
import sys
import time

from mcp.server.stdio import stdio_server

from . import gate
from .access import AccessStore
from .channel import ZaloChannel, build_server
from .state import (
    ENV_FILE_NAME,
    PidLock,
    SeenChats,
    SeenMessages,
    resolve_token,
    state_dir,
    token_lock_path,
)
from .zalo_api import (
    ZaloApiError,
    ZaloBotApi,
    ZaloClientError,
    ZaloTransientError,
    parse_update,
)

logger = logging.getLogger(__name__)

TOKEN_ENV = "ZALO_BOT_TOKEN"
POLL_TIMEOUT = 30
BACKOFF_START = 1.0
BACKOFF_MAX = 60.0

# Hard floor between polls. Zalo's getUpdates takes ONLY `timeout`, checked
# against the official docs (bot.zapps.me/docs, all ten documented methods,
# 2026-08-08): no offset, no ack/confirm endpoint, no cursor. Consumed
# updates therefore reappear on every poll, and while the queue is non-empty
# Zalo answers IMMEDIATELY instead of holding the long poll open (measured:
# ~12 req/s the moment the first message arrived). Without this floor the
# loop is a hot spin straight into a rate limit or a banned bot.
MIN_POLL_INTERVAL = 1.0


async def handle_update(
    update: object,
    *,
    api: ZaloBotApi,
    store: AccessStore,
    seen: SeenMessages,
    chats: SeenChats,
    channel: ZaloChannel,
) -> bool:
    """Process one update. Returns True when it was skipped as an
    already-seen duplicate (the normal case, Zalo replays consumed updates
    on every poll)."""
    msg = parse_update(update)
    if msg is None:
        return False
    if seen.seen(msg.message_id):
        return True
    verdict = gate.check(store, msg)
    if verdict.action == "drop":
        # Silent toward the sender, recorded for the operator: this is how
        # you find a new group's chat_id ('admin pending-chats'). stderr
        # alone is invisible under an MCP client.
        chats.record(msg)
        logger.info(
            "gate dropped message from user %s in %s chat %s",
            msg.user_id,
            msg.chat_type,
            msg.chat_id,
        )
    try:
        if verdict.action == "reply":
            await api.send_message(msg.chat_id, verdict.reply_text)
        elif verdict.action == "allow":
            await channel.push_inbound(msg)
    except ZaloApiError as exc:
        # Not marked as seen: if Zalo replays the message we retry.
        logger.error("handling message %s failed: %s", msg.message_id, exc)
        return False
    seen.mark(msg.message_id)
    return False


async def poll_loop(
    api: ZaloBotApi,
    store: AccessStore,
    seen: SeenMessages,
    chats: SeenChats,
    channel: ZaloChannel,
    *,
    clock=time.monotonic,
    sleep=asyncio.sleep,
) -> None:
    backoff = BACKOFF_START
    channel.poller_state = "running"
    try:
        while True:
            started = clock()
            try:
                result = await api.get_updates(timeout=POLL_TIMEOUT)
            except ZaloTransientError as exc:
                logger.warning("getUpdates failed (%s); retrying in %.0fs", exc, backoff)
                await sleep(backoff)
                backoff = min(backoff * 2, BACKOFF_MAX)
                continue
            except ZaloClientError as exc:
                # Our request is wrong (bad token, API change). Retrying
                # cannot help, crash loudly, message included: swallowing
                # Zalo's description once cost a whole silent-death debugging
                # session.
                if "webhook" in str(exc).lower():
                    logger.critical(
                        "getUpdates rejected: %s, this bot has a webhook"
                        " attached, and Zalo allows only one of"
                        " webhook/long-polling. Either delete the webhook"
                        " (WARNING: that breaks whatever system currently"
                        " receives it) or use a separate bot token for MCP.",
                        exc,
                    )
                else:
                    logger.critical("getUpdates rejected by Zalo, poller stopping: %s", exc)
                raise
            backoff = BACKOFF_START
            channel.note_poll()
            updates = result if isinstance(result, list) else [result] if result else []
            duplicates = 0
            for update in updates:
                if await handle_update(
                    update, api=api, store=store, seen=seen, chats=chats, channel=channel
                ):
                    duplicates += 1
            if duplicates:
                logger.debug("skipped %d already-seen update(s) this poll", duplicates)
            # Hard floor: with a non-empty queue Zalo answers instantly and
            # replays old updates, so a bare loop spins hot (see
            # MIN_POLL_INTERVAL above).
            elapsed = clock() - started
            if elapsed < MIN_POLL_INTERVAL:
                await sleep(MIN_POLL_INTERVAL - elapsed)
    finally:
        channel.poller_state = "stopped"


def _webhook_url(info: object) -> str | None:
    """Extract the webhook url from a getWebhookInfo result. The no-webhook
    shape is undocumented, so tolerate a missing/empty/odd result."""
    if not isinstance(info, dict):
        return None
    url = info.get("url")
    if isinstance(url, str) and url.strip():
        return url.strip()
    return None


async def check_webhook_clear(api: ZaloBotApi) -> None:
    """Zalo refuses getUpdates while a webhook is set. Dying here, at
    startup, with the webhook url in hand beats dying silently 30 seconds
    later in the first poll."""
    try:
        # Returns None for a clean bot (Zalo answers 404 there), that is the
        # normal path, not an error.
        info = await api.get_webhook_info()
    except ZaloApiError as exc:
        # Transient trouble only, don't block startup on it; the poll loop's
        # webhook handler still catches the real failure with guidance.
        logger.warning("getWebhookInfo failed, continuing anyway: %s", exc)
        return
    url = _webhook_url(info)
    if url:
        logger.critical(
            "this bot has a webhook set: %s, Zalo refuses getUpdates while a"
            " webhook exists, so this MCP server cannot receive messages."
            " Either delete that webhook (WARNING: doing so breaks whatever"
            " system currently receives it) or create a separate bot for MCP.",
            url,
        )
        raise SystemExit(1)


async def _amain(token: str) -> None:
    sdir = state_dir()
    # Two locks guarding two different resources. The token lock names the
    # BOT (its getUpdates queue): it is what stops two pollers with different
    # state dirs from splitting one bot's messages. The state-dir lock guards
    # access.json / seen-messages from cross-writes. Token lock first.
    token_lock = PidLock(token_lock_path(token))
    try:
        token_lock.acquire()
    except RuntimeError as exc:
        logger.critical(
            "another process is already polling THIS SAME BOT (%s)."
            " Zalo delivers each getUpdates result to only one consumer, so"
            " two pollers on one token split the messages between them, and"
            " a different ZALO_MCP_STATE_DIR does not help. Stop that"
            " process first.",
            exc,
        )
        raise SystemExit(1) from None
    pid_lock = PidLock(sdir / "poller.pid")
    try:
        pid_lock.acquire()
    except RuntimeError as exc:
        logger.critical("%s", exc)
        token_lock.release()
        raise SystemExit(1) from None
    api = ZaloBotApi(token)
    try:
        try:
            me = await api.get_me()
        except ZaloApiError as exc:
            logger.critical("getMe failed, check %s: %s", TOKEN_ENV, exc)
            raise SystemExit(1) from None
        name = me.get("display_name") or me.get("id") if isinstance(me, dict) else me
        logger.info("bot authenticated as %s; state dir %s", name, sdir)
        await check_webhook_clear(api)

        store = AccessStore(sdir / "access.json")
        store.load()  # A wildcard allowlist must refuse to run NOW, not at the first message.
        seen = SeenMessages(sdir / "seen-messages.json")
        chats = SeenChats(sdir / "seen-chats.json")
        channel = ZaloChannel(api)
        server = build_server(channel)

        stop = asyncio.Event()
        loop = asyncio.get_running_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, stop.set)

        async with stdio_server() as (read_stream, write_stream):
            init_options = server.create_initialization_options(
                experimental_capabilities={"claude/channel": {}}
            )
            tasks = [
                asyncio.create_task(
                    poll_loop(api, store, seen, chats, channel), name="zalo-poller"
                ),
                asyncio.create_task(
                    server.run(read_stream, write_stream, init_options), name="mcp-server"
                ),
                asyncio.create_task(stop.wait(), name="stop-signal"),
            ]
            done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
            for task in pending:
                task.cancel()
            await asyncio.gather(*pending, return_exceptions=True)
            for task in done:
                task.result()  # re-raise poller/server crashes (e.g. 4xx)
        logger.info("shut down cleanly")
    finally:
        await api.aclose()
        pid_lock.release()
        token_lock.release()


def run() -> None:
    logging.basicConfig(
        stream=sys.stderr,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    token = resolve_token()
    if not token:
        logger.critical(
            "no bot token. Either set %s in the environment, write %s with a"
            " line %s=<your token>, or (in Claude Code, with the token in"
            " your clipboard) run /zalo-set-token.",
            TOKEN_ENV,
            state_dir() / ENV_FILE_NAME,
            TOKEN_ENV,
        )
        raise SystemExit(2)
    asyncio.run(_amain(token))


if __name__ == "__main__":
    run()
