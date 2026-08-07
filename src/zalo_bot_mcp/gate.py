"""The single gate. Every inbound Zalo message passes through check() before
it may reach the Claude session; nothing else is allowed to forward messages.

Decisions, not side effects: the gate never talks to the network. It returns
what should happen (allow / drop / reply-with-pairing-code) and the caller
does the sending. Unknown is always dropped silently, strangers learn
nothing about whether the bot is alive.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from .access import AccessStore
from .zalo_api import InboundMessage

Action = Literal["allow", "drop", "reply"]


@dataclass(frozen=True)
class GateResult:
    action: Action
    reply_text: str | None = None


ALLOW = GateResult("allow")
DROP = GateResult("drop")


def _pairing_reply(code: str) -> str:
    return (
        f"Pairing code: {code} (expires in 1 hour). "
        "Ask the bot operator to approve it, the bot itself cannot.\n"
        f"Mã ghép nối: {code} (hết hạn sau 1 giờ). "
        "Nhờ người vận hành bot duyệt mã này."
    )


def check(store: AccessStore, msg: InboundMessage) -> GateResult:
    """Decide what to do with one inbound message.

    Raises AccessError if access.json is invalid (wildcards, bad policy):
    refusing to run beats running open.
    """
    if msg.is_bot:
        return DROP

    cfg = store.load()

    if msg.chat_type == "PRIVATE":
        policy = cfg["dmPolicy"]
        if policy == "disabled":
            return DROP
        if msg.user_id in cfg["allowFrom"]:
            return ALLOW
        if policy == "pairing":
            code = store.issue_pairing_code(msg.user_id)
            if code is not None:
                return GateResult("reply", _pairing_reply(code))
        # allowlist miss, attempt cap, or full pending slots: silence.
        return DROP

    if msg.chat_type == "GROUP":
        group = cfg["groups"].get(msg.chat_id)
        if group is None:
            return DROP
        allow_from = group.get("allowFrom", [])
        if allow_from and msg.user_id not in allow_from:
            return DROP
        return ALLOW

    return DROP
