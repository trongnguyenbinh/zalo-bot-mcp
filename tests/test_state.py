"""state.py tests: state-dir resolution, message dedupe with TTL, pid lock."""

import json
import os

import pytest

from zalo_bot_mcp.state import SEEN_TTL_SECONDS, PidLock, SeenMessages, state_dir


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
