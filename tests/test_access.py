"""access.py tests: config validation (wildcard refusal), live reload,
pairing-code lifecycle."""

import json

import pytest

from zalo_bot_mcp.access import (
    MAX_PAIR_ATTEMPTS,
    MAX_PENDING_CODES,
    PAIRING_TTL_SECONDS,
    AccessError,
    AccessStore,
)


class Clock:
    def __init__(self, t=1_000.0):
        self.t = t

    def __call__(self):
        return self.t


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def store(tmp_path, clock):
    return AccessStore(tmp_path / "access.json", now=clock)


def write(store_path, cfg):
    store_path.write_text(json.dumps(cfg), encoding="utf-8")


def base_cfg(**overrides):
    cfg = {"dmPolicy": "allowlist", "allowFrom": [], "groups": {}, "pending": {}, "pairAttempts": {}}
    cfg.update(overrides)
    return cfg


# --- validation --------------------------------------------------------------


def test_missing_file_yields_default_pairing_config(store):
    cfg = store.load()
    assert cfg["dmPolicy"] == "pairing"
    assert cfg["allowFrom"] == []


def test_wildcard_star_in_allowfrom_refuses_to_run(tmp_path, clock):
    path = tmp_path / "access.json"
    write(path, base_cfg(allowFrom=["*"]))
    with pytest.raises(AccessError, match="wildcard"):
        AccessStore(path, now=clock).load()


def test_wildcard_question_mark_refuses_to_run(tmp_path, clock):
    path = tmp_path / "access.json"
    write(path, base_cfg(allowFrom=["user-?"]))
    with pytest.raises(AccessError, match="wildcard"):
        AccessStore(path, now=clock).load()


def test_wildcard_in_group_allowfrom_refuses_to_run(tmp_path, clock):
    path = tmp_path / "access.json"
    write(path, base_cfg(groups={"g1": {"allowFrom": ["*"], "requireMention": True}}))
    with pytest.raises(AccessError, match="wildcard"):
        AccessStore(path, now=clock).load()


def test_invalid_dm_policy_rejected(tmp_path, clock):
    path = tmp_path / "access.json"
    write(path, base_cfg(dmPolicy="open-sesame"))
    with pytest.raises(AccessError, match="dmPolicy"):
        AccessStore(path, now=clock).load()


def test_corrupted_json_rejected(tmp_path, clock):
    path = tmp_path / "access.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(AccessError):
        AccessStore(path, now=clock).load()


def test_save_validates_too(store):
    with pytest.raises(AccessError):
        store.save(base_cfg(allowFrom=["*"]))


# --- live reload -------------------------------------------------------------


def test_file_edits_take_effect_without_restart(tmp_path, clock):
    path = tmp_path / "access.json"
    store = AccessStore(path, now=clock)
    write(path, base_cfg(allowFrom=["u1"]))
    assert store.load()["allowFrom"] == ["u1"]
    write(path, base_cfg(allowFrom=["u1", "u2"]))
    assert store.load()["allowFrom"] == ["u1", "u2"]


# --- pairing lifecycle -------------------------------------------------------


def test_issue_code_is_6_hex(store):
    code = store.issue_pairing_code("u1")
    assert code is not None
    assert len(code) == 6
    int(code, 16)  # raises if not hex
    pending = store.load()["pending"]
    assert pending[code]["user_id"] == "u1"


def test_expired_codes_pruned_on_load(store, clock):
    code = store.issue_pairing_code("u1")
    clock.t += PAIRING_TTL_SECONDS + 1
    assert store.load()["pending"] == {}
    # And the prune was persisted, not just in-memory.
    assert code not in store.load()["pending"]


def test_reissue_replaces_own_code_not_a_second_slot(store):
    first = store.issue_pairing_code("u1")
    second = store.issue_pairing_code("u1")
    pending = store.load()["pending"]
    assert first not in pending
    assert second in pending
    assert len(pending) == 1


def test_attempt_cap_silences_user(store):
    for _ in range(MAX_PAIR_ATTEMPTS):
        assert store.issue_pairing_code("u1") is not None
    assert store.issue_pairing_code("u1") is None


def test_pending_slot_cap(store):
    for i in range(MAX_PENDING_CODES):
        assert store.issue_pairing_code(f"u{i}") is not None
    assert store.issue_pairing_code("u-late") is None
    # Slot-cap rejection must not burn the late user's attempts: once a slot
    # frees up they can still pair.
    assert store.load()["pairAttempts"].get("u-late") is None


def test_slot_frees_after_expiry(store, clock):
    for i in range(MAX_PENDING_CODES):
        store.issue_pairing_code(f"u{i}")
    clock.t += PAIRING_TTL_SECONDS + 1
    assert store.issue_pairing_code("u-late") is not None


def test_approve_pairing_moves_user_to_allowlist(store):
    code = store.issue_pairing_code("u1")
    assert store.approve_pairing(code) == "u1"
    cfg = store.load()
    assert "u1" in cfg["allowFrom"]
    assert cfg["pending"] == {}
    assert cfg["pairAttempts"] == {}


def test_approve_unknown_or_expired_code_returns_none(store, clock):
    assert store.approve_pairing("ffffff") is None
    code = store.issue_pairing_code("u1")
    clock.t += PAIRING_TTL_SECONDS + 1
    assert store.approve_pairing(code) is None
