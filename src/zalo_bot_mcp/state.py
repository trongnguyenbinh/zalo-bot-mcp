"""State directory, message dedupe, and the poller pid lock.

Zalo's getUpdates has no offset parameter, so the Telegram-style cursor model
is impossible. Dedupe works by message_id instead: keep the set of processed
ids on disk, skip anything already seen. Callers must mark() a message only
AFTER processing it — a crash mid-processing then replays the message, and a
duplicate beats a lost message.
"""

from __future__ import annotations

import fcntl
import json
import logging
import os
import time
from collections.abc import Callable
from pathlib import Path

logger = logging.getLogger(__name__)

STATE_DIR_ENV = "ZALO_MCP_STATE_DIR"
DEFAULT_STATE_DIR = "~/.zalo-bot-mcp"

# How long a processed message_id is remembered. Zalo does not document how
# far back getUpdates may replay; a week comfortably outlasts any plausible
# replay window while keeping the file bounded.
SEEN_TTL_SECONDS = 7 * 24 * 3600


def state_dir() -> Path:
    """Resolve the state directory from $ZALO_MCP_STATE_DIR (default
    ~/.zalo-bot-mcp) and create it if needed."""
    raw = os.environ.get(STATE_DIR_ENV, "").strip() or DEFAULT_STATE_DIR
    path = Path(raw).expanduser()
    path.mkdir(parents=True, exist_ok=True)
    return path


class SeenMessages:
    """Persistent set of processed message_ids with a time-based cap.

    Only this process writes the file, so it is loaded once and kept in
    memory; every mark() persists atomically.
    """

    def __init__(
        self,
        path: str | Path,
        *,
        ttl: float = SEEN_TTL_SECONDS,
        now: Callable[[], float] = time.time,
    ) -> None:
        self._path = Path(path)
        self._ttl = ttl
        self._now = now
        self._ids: dict[str, float] = {}
        if self._path.exists():
            try:
                raw = json.loads(self._path.read_text(encoding="utf-8"))
                self._ids = {str(k): float(v) for k, v in raw.items()}
            except (OSError, ValueError, AttributeError):
                logger.warning("seen-messages file unreadable; starting fresh")
        self._prune()

    def seen(self, message_id: str) -> bool:
        return message_id in self._ids

    def mark(self, message_id: str) -> None:
        """Record a message as processed. Call AFTER processing succeeds."""
        self._ids[message_id] = self._now()
        self._prune()
        self._save()

    def _prune(self) -> None:
        cutoff = self._now() - self._ttl
        self._ids = {k: v for k, v in self._ids.items() if v > cutoff}

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_name(self._path.name + ".tmp")
        tmp.write_text(json.dumps(self._ids), encoding="utf-8")
        os.replace(tmp, self._path)


class PidLock:
    """One poller per token: two pollers sharing a token would steal each
    other's getUpdates results.

    flock-based. Signalling pids read from a file is unsafe — a stale file
    plus OS pid reuse means killing an unrelated process. The OS releases a
    flock automatically when its holder dies, so a stale file can never
    block anyone and there is no liveness guessing (or killing) at all. If
    the lock is held, the newcomer reports the holder and refuses to start;
    the user stops the old process themselves.
    """

    def __init__(self, path: str | Path) -> None:
        self._path = Path(path)
        self._fd: int | None = None

    def acquire(self) -> None:
        """Take the lock or raise RuntimeError naming the current holder.
        The fd stays open for the life of the process — closing it is what
        releases the lock."""
        self._path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(self._path, os.O_RDWR | os.O_CREAT, 0o644)
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            holder = self._read()
            os.close(fd)
            raise RuntimeError(
                f"another poller already holds {self._path}"
                f" (pid {holder if holder is not None else 'unknown'})."
                " Stop that process first, then start this one."
            ) from None
        os.ftruncate(fd, 0)
        # The pid is informational only (for the error message above) —
        # liveness comes from the flock, never from this number.
        os.write(fd, str(os.getpid()).encode("ascii"))
        self._fd = fd

    def release(self) -> None:
        """Drop the lock (closing the fd releases it) and remove the file if
        it is still ours."""
        if self._fd is None:
            return
        if self._read() == os.getpid():
            try:
                self._path.unlink()
            except OSError:
                pass
        os.close(self._fd)
        self._fd = None

    def _read(self) -> int | None:
        try:
            return int(self._path.read_text(encoding="utf-8").strip())
        except (OSError, ValueError):
            return None
