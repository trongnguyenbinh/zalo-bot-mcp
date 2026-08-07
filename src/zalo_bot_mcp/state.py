"""State directory, message dedupe, and the poller pid lock.

The dedupe set is a load-bearing pillar, not an optimization. Zalo's
getUpdates has no offset and no ack/confirm endpoint of any kind, verified
against the official docs (bot.zapps.me/docs, all ten documented methods)
and measured against a live bot: consumed updates come back on EVERY
subsequent poll, indefinitely, and there is no way to tell Zalo "done with
this one". SeenMessages is therefore the ONLY thing standing between the bot
and reprocessing every queued message on every poll cycle. That is why it
persists to disk (must survive restarts) and why its TTL just needs to
outlast Zalo's server-side queue retention, a week is comfortable.

Callers must mark() a message only AFTER processing it, a crash
mid-processing then replays the message, and a duplicate beats a lost
message.
"""

from __future__ import annotations

import fcntl
import hashlib
import json
import logging
import os
import time
from collections.abc import Callable
from pathlib import Path

logger = logging.getLogger(__name__)

STATE_DIR_ENV = "ZALO_MCP_STATE_DIR"
DEFAULT_STATE_DIR = "~/.zalo-bot-mcp"
TOKEN_KEY = "ZALO_BOT_TOKEN"
ENV_FILE_NAME = ".env"

# How long a processed message_id is remembered. Zalo does not document how
# far back getUpdates may replay; a week comfortably outlasts any plausible
# replay window while keeping the file bounded.
SEEN_TTL_SECONDS = 7 * 24 * 3600

# Cap on recorded gate-dropped chats; oldest entries fall off first.
SEEN_CHATS_MAX = 50


def state_dir() -> Path:
    """Resolve the state directory from $ZALO_MCP_STATE_DIR (default
    ~/.zalo-bot-mcp) and create it if needed."""
    raw = os.environ.get(STATE_DIR_ENV, "").strip() or DEFAULT_STATE_DIR
    path = Path(raw).expanduser()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _parse_env(text: str) -> dict[str, str]:
    """Minimal .env parser, no dependency: skip blanks and #-comments, split
    on the first '=', trim whitespace, strip one layer of matching quotes."""
    out: dict[str, str] = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        out[key.strip()] = value
    return out


def read_env_token(sdir: Path) -> str | None:
    """Read the bot token from <state_dir>/.env, if present."""
    path = sdir / ENV_FILE_NAME
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except (OSError, UnicodeDecodeError) as exc:
        logger.warning("cannot read %s: %s", path, exc)
        return None
    mode = path.stat().st_mode & 0o777
    if mode & 0o077:
        logger.warning(
            "%s permissions are %03o, wider than 0600; run: chmod 600 %s", path, mode, path
        )
    return _parse_env(text).get(TOKEN_KEY) or None


def write_env_token(sdir: Path, token: str) -> Path:
    """Write the token to <state_dir>/.env with mode 0600, preserving any
    other keys already in the file."""
    sdir.mkdir(parents=True, exist_ok=True)
    path = sdir / ENV_FILE_NAME
    entries: dict[str, str] = {}
    if path.exists():
        try:
            entries = _parse_env(path.read_text(encoding="utf-8"))
        except (OSError, UnicodeDecodeError):
            entries = {}
    entries[TOKEN_KEY] = token
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write("\n".join(f"{k}={v}" for k, v in entries.items()) + "\n")
    os.chmod(path, 0o600)  # tighten a pre-existing wider file too
    return path


def resolve_token() -> str | None:
    """Token lookup order: $ZALO_BOT_TOKEN, then <state_dir>/.env."""
    token = os.environ.get(TOKEN_KEY, "").strip()
    if token:
        return token
    return read_env_token(state_dir())


def token_lock_path(token: str) -> Path:
    """Path of the per-BOT lock file, keyed by a truncated token hash.

    The resource two pollers actually fight over is one bot's getUpdates
    queue, identified by the token; the state dir is just a proxy and two
    different state dirs sharing one token slip right past a state-dir lock
    (it happened). This lock names the bot itself.

    It lives under the user's XDG cache dir, not the system temp dir: temp
    cleaners delete-and-recreate files, and a recreated lock file is a new
    inode, so a second process can flock it while the first still holds the
    old one. The cache dir is never auto-cleaned and is chmod 0700, so no
    other user can squat the lock either. Only the truncated hash ever
    touches disk; the token itself does not.
    """
    cache_root = os.environ.get("XDG_CACHE_HOME", "").strip() or "~/.cache"
    lock_dir = Path(cache_root).expanduser() / "zalo-bot-mcp"
    lock_dir.mkdir(parents=True, exist_ok=True)
    os.chmod(lock_dir, 0o700)
    digest = hashlib.sha256(token.encode("utf-8")).hexdigest()[:16]
    return lock_dir / f"{digest}.lock"


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


class SeenChats:
    """Chats the gate has DROPPED, recorded so the operator can find a new
    group's chat_id via 'zalo-bot-mcp-admin pending-chats' (stderr is
    invisible when the server runs under an MCP client, and Zalo's queue
    may already be drained, so a log line alone strands the operator).

    SECURITY: this file is a read-only signal for a HUMAN. Appearing in it
    grants nothing whatsoever; access is only ever granted by the operator
    typing group-add or allow in their terminal. Its content comes straight
    from unauthenticated strangers, so it must never be wired into any
    automatic approval path.
    """

    def __init__(self, path: str | Path, *, now: Callable[[], float] = time.time) -> None:
        self._path = Path(path)
        self._now = now

    def load(self) -> dict[str, dict]:
        if not self._path.exists():
            return {}
        try:
            raw = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            logger.warning("seen-chats file unreadable; starting fresh")
            return {}
        if not isinstance(raw, dict):
            logger.warning("seen-chats file has an unexpected shape; starting fresh")
            return {}
        return raw

    def record(self, msg) -> None:
        """Note one dropped message. Same chat again updates the timestamp
        and count instead of adding a row."""
        chats = self.load()
        entry = chats.get(msg.chat_id) or {"count": 0}
        entry.update(
            {
                "chat_type": msg.chat_type,
                "user": msg.display_name or msg.user_id,
                "user_id": msg.user_id,
                "last_seen": self._now(),
                "count": entry["count"] + 1,
            }
        )
        chats[msg.chat_id] = entry
        if len(chats) > SEEN_CHATS_MAX:
            oldest_first = sorted(chats, key=lambda cid: chats[cid].get("last_seen", 0))
            for cid in oldest_first[: len(chats) - SEEN_CHATS_MAX]:
                del chats[cid]
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_name(self._path.name + ".tmp")
        tmp.write_text(json.dumps(chats, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp, self._path)


class PidLock:
    """One poller per token: two pollers sharing a token would steal each
    other's getUpdates results.

    flock-based. Signalling pids read from a file is unsafe, a stale file
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
        The fd stays open for the life of the process, closing it is what
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
        # The pid is informational only (for the error message above);
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
