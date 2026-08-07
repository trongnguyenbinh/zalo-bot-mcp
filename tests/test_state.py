"""state.py tests: state-dir resolution, message dedupe with TTL, pid lock,
per-token lock."""

import json
import os
import stat

import pytest

from zalo_bot_mcp.state import (
    SEEN_CHATS_MAX,
    SEEN_TTL_SECONDS,
    PidLock,
    SeenChats,
    SeenMessages,
    read_env_token,
    resolve_token,
    state_dir,
    token_lock_path,
    write_env_token,
)
from zalo_bot_mcp.zalo_api import InboundMessage


def inbound(chat="c1", chat_type="GROUP", user="u1", name="Someone"):
    return InboundMessage(
        user_id=user,
        display_name=name,
        is_bot=False,
        chat_id=chat,
        chat_type=chat_type,
        text="hi",
        message_id="m1",
        date=0,
    )


class Clock:
    def __init__(self, t=1_000_000.0):
        self.t = t

    def __call__(self):
        return self.t


# --- state_dir ---------------------------------------------------------------


def test_state_dir_env_override(monkeypatch, tmp_path):
    custom = tmp_path / "custom-state"
    monkeypatch.setenv("ZALO_MCP_STATE_DIR", str(custom))
    assert state_dir() == custom
    assert custom.is_dir()


def test_state_dir_default_under_home(monkeypatch, tmp_path):
    monkeypatch.delenv("ZALO_MCP_STATE_DIR", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    assert state_dir() == tmp_path / ".zalo-bot-mcp"


# --- SeenMessages ------------------------------------------------------------


@pytest.fixture
def clock():
    return Clock()


def test_seen_roundtrip(tmp_path, clock):
    seen = SeenMessages(tmp_path / "seen.json", now=clock)
    assert not seen.seen("m1")
    seen.mark("m1")
    assert seen.seen("m1")
    assert not seen.seen("m2")


def test_seen_persists_across_instances(tmp_path, clock):
    path = tmp_path / "seen.json"
    SeenMessages(path, now=clock).mark("m1")
    assert SeenMessages(path, now=clock).seen("m1")


def test_seen_prunes_old_ids_by_ttl(tmp_path, clock):
    path = tmp_path / "seen.json"
    seen = SeenMessages(path, now=clock)
    seen.mark("old")
    clock.t += SEEN_TTL_SECONDS + 1
    seen.mark("new")
    assert not seen.seen("old")
    assert seen.seen("new")
    # Pruned on disk too, not just in memory.
    assert "old" not in json.loads(path.read_text())


def test_seen_expired_ids_dropped_on_load(tmp_path, clock):
    path = tmp_path / "seen.json"
    path.write_text(json.dumps({"ancient": clock.t - SEEN_TTL_SECONDS - 1, "fresh": clock.t}))
    seen = SeenMessages(path, now=clock)
    assert not seen.seen("ancient")
    assert seen.seen("fresh")


def test_seen_survives_corrupt_file(tmp_path, clock):
    path = tmp_path / "seen.json"
    path.write_text("{not json")
    seen = SeenMessages(path, now=clock)
    assert not seen.seen("m1")
    seen.mark("m1")  # and it can write again
    assert SeenMessages(path, now=clock).seen("m1")


# --- token from env / .env file ----------------------------------------------


@pytest.fixture
def sdir(tmp_path, monkeypatch):
    monkeypatch.setenv("ZALO_MCP_STATE_DIR", str(tmp_path))
    monkeypatch.delenv("ZALO_BOT_TOKEN", raising=False)
    return tmp_path


def test_resolve_token_env_var_wins_over_file(sdir, monkeypatch):
    write_env_token(sdir, "file-token")
    monkeypatch.setenv("ZALO_BOT_TOKEN", "env-token")
    assert resolve_token() == "env-token"


def test_resolve_token_falls_back_to_env_file(sdir):
    write_env_token(sdir, "file-token")
    assert resolve_token() == "file-token"


def test_resolve_token_missing_both(sdir):
    assert resolve_token() is None


def test_env_file_parsing_comments_blanks_quotes(sdir):
    (sdir / ".env").write_text(
        '# comment\n\nOTHER=stuff\nZALO_BOT_TOKEN = "quoted-token=with=equals"\n'
    )
    os.chmod(sdir / ".env", 0o600)
    assert read_env_token(sdir) == "quoted-token=with=equals"


def test_env_file_without_token_line(sdir):
    (sdir / ".env").write_text("SOMETHING=else\nnot a kv line\n")
    os.chmod(sdir / ".env", 0o600)
    assert read_env_token(sdir) is None


def test_env_file_not_utf8_does_not_crash(sdir):
    (sdir / ".env").write_bytes(b"\xff\xfe\x00garbage")
    os.chmod(sdir / ".env", 0o600)
    assert read_env_token(sdir) is None


def test_write_env_token_mode_600_and_preserves_other_keys(sdir):
    (sdir / ".env").write_text("KEEP=me\n")
    path = write_env_token(sdir, "tok-1")
    assert stat.S_IMODE(path.stat().st_mode) == 0o600
    content = path.read_text()
    assert "KEEP=me" in content
    assert "ZALO_BOT_TOKEN=tok-1" in content
    write_env_token(sdir, "tok-2")
    assert read_env_token(sdir) == "tok-2"


def test_read_env_warns_on_loose_permissions_but_still_works(sdir, caplog):
    write_env_token(sdir, "tok")
    os.chmod(sdir / ".env", 0o644)
    with caplog.at_level("WARNING"):
        assert read_env_token(sdir) == "tok"
    assert "chmod 600" in caplog.text


# --- SeenChats ---------------------------------------------------------------


def test_seen_chats_records_dropped_chat(tmp_path, clock):
    chats = SeenChats(tmp_path / "chats.json", now=clock)
    chats.record(inbound(chat="g1", user="u9", name="Ed"))
    entry = SeenChats(tmp_path / "chats.json", now=clock).load()["g1"]
    assert entry["chat_type"] == "GROUP"
    assert entry["user"] == "Ed"
    assert entry["user_id"] == "u9"
    assert entry["count"] == 1
    assert entry["last_seen"] == clock.t


def test_seen_chats_repeat_updates_instead_of_duplicating(tmp_path, clock):
    chats = SeenChats(tmp_path / "chats.json", now=clock)
    chats.record(inbound(chat="g1"))
    clock.t += 100
    chats.record(inbound(chat="g1"))
    data = chats.load()
    assert len(data) == 1
    assert data["g1"]["count"] == 2
    assert data["g1"]["last_seen"] == clock.t


def test_seen_chats_caps_at_max_dropping_oldest(tmp_path, clock):
    chats = SeenChats(tmp_path / "chats.json", now=clock)
    for i in range(SEEN_CHATS_MAX + 5):
        clock.t += 1  # each entry newer than the last
        chats.record(inbound(chat=f"c{i}"))
    data = chats.load()
    assert len(data) == SEEN_CHATS_MAX
    for i in range(5):
        assert f"c{i}" not in data  # the five oldest fell off
    assert f"c{SEEN_CHATS_MAX + 4}" in data


def test_seen_chats_corrupt_file_starts_fresh(tmp_path, clock):
    path = tmp_path / "chats.json"
    path.write_text("{broken")
    chats = SeenChats(path, now=clock)
    assert chats.load() == {}
    chats.record(inbound(chat="g1"))  # and it can write again
    assert "g1" in chats.load()


# --- PidLock -----------------------------------------------------------------


def test_acquire_writes_own_pid(tmp_path):
    path = tmp_path / "poller.pid"
    lock = PidLock(path)
    lock.acquire()
    try:
        assert int(path.read_text()) == os.getpid()
    finally:
        lock.release()


def test_second_lock_on_separate_fd_fails_while_first_held(tmp_path):
    path = tmp_path / "poller.pid"
    first = PidLock(path)
    first.acquire()
    try:
        second = PidLock(path)
        with pytest.raises(RuntimeError, match=str(os.getpid())):
            second.acquire()
    finally:
        first.release()


def test_lock_free_again_after_release(tmp_path):
    path = tmp_path / "poller.pid"
    first = PidLock(path)
    first.acquire()
    first.release()
    second = PidLock(path)
    second.acquire()  # must not raise
    try:
        assert int(path.read_text()) == os.getpid()
    finally:
        second.release()


def test_stale_file_from_dead_process_does_not_block(tmp_path):
    # A leftover file whose writer is gone holds no flock — acquire must
    # succeed without any liveness guessing or signalling.
    path = tmp_path / "poller.pid"
    path.write_text("54321")
    lock = PidLock(path)
    lock.acquire()
    try:
        assert int(path.read_text()) == os.getpid()
    finally:
        lock.release()


def test_release_removes_own_pid_file(tmp_path):
    path = tmp_path / "poller.pid"
    lock = PidLock(path)
    lock.acquire()
    lock.release()
    assert not path.exists()


def test_release_leaves_someone_elses_pid_file(tmp_path):
    path = tmp_path / "poller.pid"
    lock = PidLock(path)
    lock.acquire()
    path.write_text("99999")  # another process took the path over
    lock.release()
    assert path.exists()


def test_release_without_acquire_is_a_noop(tmp_path):
    PidLock(tmp_path / "poller.pid").release()  # must not raise


# --- per-token lock ----------------------------------------------------------


@pytest.fixture
def cache(tmp_path, monkeypatch):
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    return tmp_path / "cache"


def test_same_token_blocked_even_with_different_state_dirs(cache):
    """The exact incident this lock exists for: two processes, two different
    ZALO_MCP_STATE_DIR values, one token. The state-dir locks don't collide,
    but the token lock must."""
    first = PidLock(token_lock_path("tok-shared"))
    first.acquire()  # process 1, state dir A
    try:
        second = PidLock(token_lock_path("tok-shared"))  # process 2, state dir B
        with pytest.raises(RuntimeError):
            second.acquire()
    finally:
        first.release()


def test_different_tokens_do_not_conflict(cache):
    a = PidLock(token_lock_path("tok-a"))
    b = PidLock(token_lock_path("tok-b"))
    a.acquire()
    try:
        b.acquire()  # must not raise
        b.release()
    finally:
        a.release()


def test_token_never_appears_in_lock_path_or_file(cache):
    token = "super-secret-token-material-xyz"
    path = token_lock_path(token)
    assert token not in str(path)
    lock = PidLock(path)
    lock.acquire()
    try:
        assert token not in path.read_text()
        int(path.read_text())  # content is just the pid
    finally:
        lock.release()


def test_token_lock_dir_location_and_permissions(cache):
    path = token_lock_path("tok-x")
    assert path.parent == cache / "zalo-bot-mcp"
    assert path.name.endswith(".lock")
    assert len(path.stem) == 16
    int(path.stem, 16)  # 16 hex chars of the hash
    assert stat.S_IMODE(path.parent.stat().st_mode) == 0o700


def test_token_lock_defaults_to_home_cache(monkeypatch, tmp_path):
    monkeypatch.delenv("XDG_CACHE_HOME", raising=False)
    monkeypatch.setenv("HOME", str(tmp_path))
    assert token_lock_path("tok-x").parent == tmp_path / ".cache" / "zalo-bot-mcp"
