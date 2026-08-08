"""admin CLI tests — every command, against a temp state dir only."""

import io
import stat

import pytest

from zalo_bot_mcp import admin
from zalo_bot_mcp.access import AccessStore
from zalo_bot_mcp.admin import main
from zalo_bot_mcp.state import SeenChats, read_env_token
from zalo_bot_mcp.zalo_api import InboundMessage, ZaloClientError


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


@pytest.fixture
def state(tmp_path, monkeypatch):
    monkeypatch.setenv("ZALO_MCP_STATE_DIR", str(tmp_path))
    return tmp_path


@pytest.fixture
def store(state):
    return AccessStore(state / "access.json")


def test_list_default_config(state, capsys):
    assert main(["list"]) == 0
    out = capsys.readouterr().out
    assert "dmPolicy: pairing" in out
    assert "(empty)" in out
    assert "(none)" in out


def test_allow_then_list(state, capsys):
    assert main(["allow", "u1"]) == 0
    assert main(["list"]) == 0
    assert "u1" in capsys.readouterr().out


def test_allow_is_idempotent(state, store):
    assert main(["allow", "u1"]) == 0
    assert main(["allow", "u1"]) == 0
    assert store.load()["allowFrom"] == ["u1"]


def test_allow_clears_pending_and_attempts(state, store):
    code = store.issue_pairing_code("u1")
    assert main(["allow", "u1"]) == 0
    cfg = store.load()
    assert code not in cfg["pending"]
    assert "u1" not in cfg["pairAttempts"]


def test_revoke(state, store):
    main(["allow", "u1"])
    assert main(["revoke", "u1"]) == 0
    assert store.load()["allowFrom"] == []


def test_revoke_unknown_user_fails(state, capsys):
    assert main(["revoke", "ghost"]) == 1
    assert "not in allowFrom" in capsys.readouterr().err


def test_corrupt_access_json_reports_cleanly(state, capsys):
    (state / "access.json").write_text('{"dmPolicy": "pairing"}garbage')
    assert main(["list"]) == 1
    err = capsys.readouterr().err
    assert "access.json" in err
    assert "delete it to start over" in err


def test_invalid_policy_in_file_reports_cleanly(state, capsys):
    (state / "access.json").write_text('{"dmPolicy": "everyone"}')
    assert main(["list"]) == 1
    assert "dmPolicy must be one of" in capsys.readouterr().err


def test_policy_switch_to_disabled(state, store, capsys):
    assert main(["policy", "disabled"]) == 0
    assert store.load()["dmPolicy"] == "disabled"
    assert "pairing -> disabled" in capsys.readouterr().out


def test_policy_allowlist_refused_while_allowfrom_empty(state, store, capsys):
    assert main(["policy", "allowlist"]) == 1
    assert store.load()["dmPolicy"] == "pairing"
    assert "allowFrom is empty" in capsys.readouterr().err


def test_policy_allowlist_allowed_once_someone_is_approved(state, store):
    main(["allow", "u1"])
    assert main(["policy", "allowlist"]) == 0
    assert store.load()["dmPolicy"] == "allowlist"


def test_policy_same_value_is_a_noop(state, store, capsys):
    assert main(["policy", "pairing"]) == 0
    assert "already pairing" in capsys.readouterr().out


def test_policy_rejects_unknown_value(state):
    with pytest.raises(SystemExit):
        main(["policy", "everyone"])


def test_approve_pairing_code(state, store, capsys):
    code = store.issue_pairing_code("u9")
    assert main(["approve", code]) == 0
    assert "u9" in capsys.readouterr().out
    assert "u9" in store.load()["allowFrom"]


def test_approve_bad_code_fails(state, capsys):
    assert main(["approve", "ffffff"]) == 1
    assert "unknown or expired" in capsys.readouterr().err


def test_list_shows_pending_code_with_time_left(state, store, capsys):
    code = store.issue_pairing_code("u9")
    assert main(["list"]) == 0
    out = capsys.readouterr().out
    assert code in out
    assert "u9" in out
    assert "expires in" in out


def test_group_add_and_remove(state, store):
    assert main(["group-add", "g1"]) == 0
    assert store.load()["groups"]["g1"] == {"allowFrom": [], "requireMention": True}
    assert main(["group-remove", "g1"]) == 0
    assert store.load()["groups"] == {}


def test_group_add_is_idempotent(state, store):
    main(["group-add", "g1"])
    assert main(["group-add", "g1"]) == 0
    assert list(store.load()["groups"]) == ["g1"]


def test_group_remove_unknown_fails(state, capsys):
    assert main(["group-remove", "g-ghost"]) == 1
    assert "not configured" in capsys.readouterr().err


# --- pending-chats -----------------------------------------------------------


def test_pending_chats_empty(state, capsys):
    assert main(["pending-chats"]) == 0
    assert "no blocked chats" in capsys.readouterr().out


def test_pending_chats_lists_blocked_and_suggests_commands(state, capsys):
    chats = SeenChats(state / "seen-chats.json")
    chats.record(inbound(chat="g-group", chat_type="GROUP", user="u1", name="Ed"))
    chats.record(inbound(chat="dm-1", chat_type="PRIVATE", user="u2", name="Someone"))
    assert main(["pending-chats"]) == 0
    out = capsys.readouterr().out
    assert "g-group" in out
    assert "GROUP" in out
    assert "Ed" in out
    # Actionable suggestions with the exact ids filled in.
    assert "zalo-bot-mcp-admin group-add g-group" in out
    assert "zalo-bot-mcp-admin allow u2" in out


# --- set-token ---------------------------------------------------------------


class FakeApi:
    """Stands in for ZaloBotApi in set-token tests."""

    reject = False

    def __init__(self, token, **kwargs):
        self.token = token

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc_info):
        return None

    async def get_me(self):
        if FakeApi.reject:
            raise ZaloClientError("getMe: HTTP 401: unauthorized")
        return {"id": "bot-1", "display_name": "TestBot"}


@pytest.fixture
def fake_api(monkeypatch):
    FakeApi.reject = False
    monkeypatch.setattr(admin, "ZaloBotApi", FakeApi)
    return FakeApi


def feed_stdin(monkeypatch, text):
    monkeypatch.setattr("sys.stdin", io.StringIO(text))  # isatty() is False


def test_set_token_verifies_then_writes_0600(state, fake_api, monkeypatch, capsys):
    feed_stdin(monkeypatch, "sekrit-token\n")
    assert main(["set-token"]) == 0
    out = capsys.readouterr().out
    assert "TestBot" in out
    assert "sekrit-token" not in out  # the token itself is never printed
    assert read_env_token(state) == "sekrit-token"
    assert stat.S_IMODE((state / ".env").stat().st_mode) == 0o600


def test_set_token_rejected_token_not_written(state, fake_api, monkeypatch, capsys):
    fake_api.reject = True
    feed_stdin(monkeypatch, "bad-token\n")
    assert main(["set-token"]) == 1
    assert "nothing written" in capsys.readouterr().err
    assert not (state / ".env").exists()


def test_set_token_empty_stdin_fails(state, fake_api, monkeypatch, capsys):
    feed_stdin(monkeypatch, "\n")
    assert main(["set-token"]) == 1
    assert "no token" in capsys.readouterr().err
    assert not (state / ".env").exists()


def test_set_token_reports_replacing_existing(state, fake_api, monkeypatch, capsys):
    feed_stdin(monkeypatch, "token-one\n")
    assert main(["set-token"]) == 0
    capsys.readouterr()
    feed_stdin(monkeypatch, "token-two\n")
    assert main(["set-token"]) == 0
    out = capsys.readouterr().out
    assert "replaced the existing token" in out
    assert "token-two" not in out
    assert read_env_token(state) == "token-two"


def test_pending_chats_newest_first(state, capsys):
    class Clock:
        t = 1000.0

        def __call__(self):
            return self.t

    clock = Clock()
    chats = SeenChats(state / "seen-chats.json", now=clock)
    chats.record(inbound(chat="older", chat_type="GROUP"))
    clock.t += 500
    chats.record(inbound(chat="newer", chat_type="GROUP"))
    assert main(["pending-chats"]) == 0
    out = capsys.readouterr().out
    assert out.index("newer") < out.index("older")
