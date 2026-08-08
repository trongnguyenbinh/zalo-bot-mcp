"""Read/write access.json, the access-control state.

The file is reloaded on every call, so operators can edit it while the server
runs and changes take effect immediately. Expired pairing codes are pruned on
every load. A wildcard anywhere in an allowFrom list is a fatal config error:
an open allowlist means anyone can drive the bot, and it is exactly the kind
of "temporary" setting people forget to undo.
"""

from __future__ import annotations

import copy
import json
import os
import secrets
import time
from collections.abc import Callable
from pathlib import Path
from typing import Any

PAIRING_TTL_SECONDS = 3600
MAX_PENDING_CODES = 3
MAX_PAIR_ATTEMPTS = 2
_WILDCARD_CHARS = ("*", "?")

DM_POLICIES = ("pairing", "allowlist", "disabled")

DEFAULT_CONFIG: dict[str, Any] = {
    "dmPolicy": "pairing",
    "allowFrom": [],
    "groups": {},
    "pending": {},
    "pairAttempts": {},
}


class AccessError(Exception):
    """access.json is invalid. Refuse to run rather than guess."""


def _check_allow_list(entries: Any, where: str) -> None:
    if not isinstance(entries, list):
        raise AccessError(f"{where}: allowFrom must be a list")
    for entry in entries:
        if not isinstance(entry, str):
            raise AccessError(f"{where}: allowFrom entries must be strings, got {entry!r}")
        if any(ch in entry for ch in _WILDCARD_CHARS):
            raise AccessError(
                f"{where}: wildcard {entry!r} in allowFrom, refusing to run. "
                "List explicit user ids only."
            )


def validate(cfg: Any) -> None:
    if not isinstance(cfg, dict):
        raise AccessError("access.json root must be an object")
    if cfg.get("dmPolicy", "pairing") not in DM_POLICIES:
        raise AccessError(f"dmPolicy must be one of {DM_POLICIES}, got {cfg.get('dmPolicy')!r}")
    _check_allow_list(cfg.get("allowFrom", []), "dm")
    groups = cfg.get("groups", {})
    if not isinstance(groups, dict):
        raise AccessError("groups must be an object keyed by group id")
    for gid, group in groups.items():
        if not isinstance(group, dict):
            raise AccessError(f"groups[{gid!r}] must be an object")
        _check_allow_list(group.get("allowFrom", []), f"groups[{gid!r}]")


class AccessStore:
    def __init__(self, path: str | Path, *, now: Callable[[], float] = time.time) -> None:
        self._path = Path(path)
        self._now = now

    def load(self) -> dict[str, Any]:
        """Read, validate, and prune expired pairing codes. Reloads from disk
        every call by design."""
        if not self._path.exists():
            return copy.deepcopy(DEFAULT_CONFIG)
        try:
            cfg = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise AccessError(f"cannot read {self._path}: {exc}") from exc
        validate(cfg)
        for key, default in DEFAULT_CONFIG.items():
            cfg.setdefault(key, copy.deepcopy(default))
        if self._prune_expired(cfg):
            self.save(cfg)
        return cfg

    def save(self, cfg: dict[str, Any]) -> None:
        validate(cfg)
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._path.with_name(self._path.name + ".tmp")
        tmp.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(tmp, self._path)

    def _prune_expired(self, cfg: dict[str, Any]) -> bool:
        now = self._now()
        pending = cfg["pending"]
        expired = [code for code, entry in pending.items() if entry.get("expires", 0) <= now]
        for code in expired:
            del pending[code]
        return bool(expired)

    def issue_pairing_code(self, user_id: str) -> str | None:
        """Issue a pairing code for user_id, or None if they've hit the
        attempt cap or all pending slots are taken.

        A user re-requesting replaces their old code instead of taking a
        second slot. Hitting the slot cap does not count as an attempt, the
        user never received a code.
        """
        cfg = self.load()
        attempts = cfg["pairAttempts"].get(user_id, 0)
        if attempts >= MAX_PAIR_ATTEMPTS:
            return None
        pending = cfg["pending"]
        for code in [c for c, e in pending.items() if e.get("user_id") == user_id]:
            del pending[code]
        if len(pending) >= MAX_PENDING_CODES:
            return None
        code = secrets.token_hex(3)
        pending[code] = {"user_id": user_id, "expires": self._now() + PAIRING_TTL_SECONDS}
        cfg["pairAttempts"][user_id] = attempts + 1
        self.save(cfg)
        return code

    def approve_pairing(self, code: str) -> str | None:
        """Operator-side approval: move the code's user into allowFrom.
        Returns the user id, or None if the code is unknown/expired.

        Never call this from anything a Zalo message can influence, approval
        happens out of band, by the operator, full stop.
        """
        cfg = self.load()
        entry = cfg["pending"].pop(code, None)
        if entry is None:
            return None
        user_id = str(entry["user_id"])
        if user_id not in cfg["allowFrom"]:
            cfg["allowFrom"].append(user_id)
        cfg["pairAttempts"].pop(user_id, None)
        self.save(cfg)
        return user_id
