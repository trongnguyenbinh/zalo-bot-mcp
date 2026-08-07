"""gate.py tests — the eight required scenarios plus the edges around them.
No network anywhere."""

import json
import re

import pytest

from zalo_bot_mcp.access import (
    MAX_PAIR_ATTEMPTS,
    MAX_PENDING_CODES,
    PAIRING_TTL_SECONDS,
    AccessError,
    AccessStore,
)
from zalo_bot_mcp.gate import check
from zalo_bot_mcp.zalo_api import InboundMessage


class Clock:
    def __init__(self, t=1_000.0):
        self.t = t

    def __call__(self):
        return self.t


@pytest.fixture
def clock():
    return Clock()


@pytest.fixture
def path(tmp_path):
    return tmp_path / "access.json"


@pytest.fixture
def store(path, clock):
    return AccessStore(path, now=clock)


def write(path, **overrides):
    cfg = {"dmPolicy": "pairing", "allowFrom": [], "groups": {}, "pending": {}, "pairAttempts": {}}
    cfg.update(overrides)
    path.write_text(json.dumps(cfg), encoding="utf-8")


def msg(user="u1", chat="c1", chat_type="PRIVATE", is_bot=False):
    return InboundMessage(
        user_id=user,
        display_name="Someone",
        is_bot=is_bot,
        chat_id=chat,
        chat_type=chat_type,
        text="hi",
        message_id="m1",
        date=0,
    )


# 1. Stranger ----------------------------------------------------------------


def test_stranger_under_pairing_gets_code_and_message_dropped(path, store):
    write(path, dmPolicy="pairing")
    result = check(store, msg(user="stranger"))
    assert result.action == "reply"
    code = re.search(r"\b([0-9a-f]{6})\b", result.reply_text).group(1)
    assert store.load()["pending"][code]["user_id"] == "stranger"


def test_stranger_under_allowlist_dropped_silently(path, store):
    write(path, dmPolicy="allowlist", allowFrom=["someone-else"])
    assert check(store, msg(user="stranger")).action == "drop"


# 2. Allowlisted user ---------------------------------------------------------


def test_allowlisted_user_passes(path, store):
    write(path, dmPolicy="allowlist", allowFrom=["u1"])
    assert check(store, msg(user="u1")).action == "allow"


def test_allowlisted_user_passes_under_pairing_policy_too(path, store):
    write(path, dmPolicy="pairing", allowFrom=["u1"])
    assert check(store, msg(user="u1")).action == "allow"


# 3. Unconfigured group -------------------------------------------------------


def test_unconfigured_group_dropped(path, store):
    write(path, groups={})
    assert check(store, msg(chat="g-unknown", chat_type="GROUP")).action == "drop"


# 4. Group with allowFrom -----------------------------------------------------


def test_group_allowfrom_admits_listed_user_only(path, store):
    write(path, groups={"g1": {"allowFrom": ["u1"], "requireMention": True}})
    assert check(store, msg(user="u1", chat="g1", chat_type="GROUP")).action == "allow"
    assert check(store, msg(user="u2", chat="g1", chat_type="GROUP")).action == "drop"


def test_group_with_empty_allowfrom_admits_any_member(path, store):
    write(path, groups={"g1": {"allowFrom": [], "requireMention": True}})
    assert check(store, msg(user="anyone", chat="g1", chat_type="GROUP")).action == "allow"


# 5. Expired code -------------------------------------------------------------


def test_expired_code_cleaned_and_user_can_repair_within_attempts(path, store, clock):
    write(path, dmPolicy="pairing")
    first = check(store, msg(user="s1"))
    assert first.action == "reply"
    clock.t += PAIRING_TTL_SECONDS + 1
    assert store.load()["pending"] == {}
    second = check(store, msg(user="s1"))
    assert second.action == "reply"  # attempt 2 of 2
    assert second.reply_text != first.reply_text


# 6. Pending-slot cap ---------------------------------------------------------


def test_fourth_stranger_dropped_when_three_codes_pending(path, store):
    write(path, dmPolicy="pairing")
    for i in range(MAX_PENDING_CODES):
        assert check(store, msg(user=f"s{i}")).action == "reply"
    assert check(store, msg(user="s-late")).action == "drop"


# 7. Attempt cap --------------------------------------------------------------


def test_third_message_from_same_stranger_goes_silent(path, store):
    write(path, dmPolicy="pairing")
    for _ in range(MAX_PAIR_ATTEMPTS):
        assert check(store, msg(user="pest")).action == "reply"
    assert check(store, msg(user="pest")).action == "drop"


# 8. Wildcard refusal ---------------------------------------------------------


def test_wildcard_allowlist_refuses_to_run(path, store):
    write(path, dmPolicy="allowlist", allowFrom=["*"])
    with pytest.raises(AccessError, match="wildcard"):
        check(store, msg(user="anyone"))


# Edges -----------------------------------------------------------------------


def test_bot_sender_dropped_even_if_allowlisted(path, store):
    write(path, dmPolicy="allowlist", allowFrom=["u1"])
    assert check(store, msg(user="u1", is_bot=True)).action == "drop"


def test_disabled_policy_drops_everyone_including_allowlisted(path, store):
    write(path, dmPolicy="disabled", allowFrom=["u1"])
    assert check(store, msg(user="u1")).action == "drop"


def test_unknown_chat_type_dropped(path, store):
    write(path, allowFrom=["u1"])
    assert check(store, msg(user="u1", chat_type="CHANNEL")).action == "drop"


def test_config_edits_apply_between_messages_without_restart(path, store):
    write(path, dmPolicy="allowlist", allowFrom=[])
    assert check(store, msg(user="u1")).action == "drop"
    write(path, dmPolicy="allowlist", allowFrom=["u1"])
    assert check(store, msg(user="u1")).action == "allow"
