"""Wire everything together: the Zalo poller and the MCP stdio server run
side by side in one process.

stdout belongs to the MCP protocol — all human-facing output goes to stderr
via logging, and this process never sends alerts anywhere but Zalo itself.
"""

from __future__ import annotations

import asyncio
import logging
import os
import signal
import sys

from mcp.server.stdio import stdio_server

from . import gate
from .access import AccessStore
from .channel import ZaloChannel, build_server
from .state import PidLock, SeenMessages, state_dir
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


async def handle_update(
    update: object,
    *,
    api: ZaloBotApi,
    store: AccessStore,
    seen: SeenMessages,
    channel: ZaloChannel,
) -> None:
    msg = parse_update(update)
    if msg is None:
        return
    if seen.seen(msg.message_id):
        return
    verdict = gate.check(store, msg)
    try:
        if verdict.action == "reply":
            await api.send_message(msg.chat_id, verdict.reply_text)
        elif verdict.action == "allow":
            await channel.push_inbound(msg)
    except ZaloApiError as exc:
        # Not marked as seen: if Zalo replays the message we retry.
        logger.error("handling message %s failed: %s", msg.message_id, exc)
        return
    seen.mark(msg.message_id)


async def poll_loop(
    api: ZaloBotApi, store: AccessStore, seen: SeenMessages, channel: ZaloChannel
) -> None:
    backoff = BACKOFF_START
    channel.poller_state = "running"
    try:
        while True:
            try:
                result = await api.get_updates(timeout=POLL_TIMEOUT)
            except ZaloTransientError as exc:
                logger.warning("getUpdates failed (%s); retrying in %.0fs", exc, backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, BACKOFF_MAX)
                continue
            except ZaloClientError:
                # Our request is wrong (bad token, API change). Retrying
                # cannot help — crash loudly, the error propagates to run().
                logger.critical("getUpdates rejected by Zalo; poller stopping")
                raise
            backoff = BACKOFF_START
            channel.note_poll()
            updates = result if isinstance(result, list) else [result] if result else []
            for update in updates:
                await handle_update(
                    update, api=api, store=store, seen=seen, channel=channel
                )
    finally:
        channel.poller_state = "stopped"


async def _amain(token: str) -> None:
    sdir = state_dir()
    pid_lock = PidLock(sdir / "poller.pid")
    try:
        pid_lock.acquire()
    except RuntimeError as exc:
        logger.critical("%s", exc)
        raise SystemExit(1) from None
    api = ZaloBotApi(token)
    try:
        try:
            me = await api.get_me()
        except ZaloApiError as exc:
            logger.critical("getMe failed — check %s: %s", TOKEN_ENV, exc)
            raise SystemExit(1) from None
        name = me.get("display_name") or me.get("id") if isinstance(me, dict) else me
        logger.info("bot authenticated as %s; state dir %s", name, sdir)

        store = AccessStore(sdir / "access.json")
        store.load()  # A wildcard allowlist must refuse to run NOW, not at the first message.
        seen = SeenMessages(sdir / "seen-messages.json")
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
                    poll_loop(api, store, seen, channel), name="zalo-poller"
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


def run() -> None:
    logging.basicConfig(
        stream=sys.stderr,
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    token = os.environ.get(TOKEN_ENV, "").strip()
    if not token:
        logger.critical("%s is not set; cannot start", TOKEN_ENV)
        raise SystemExit(2)
    asyncio.run(_amain(token))


if __name__ == "__main__":
    run()
