from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from homeassistant.core import HomeAssistant

from .const import CONF_FILE, ROLES


def _config_path(hass: HomeAssistant) -> Path:
    return Path(hass.config.path(CONF_FILE))


def _normalise_user(raw: dict[str, Any]) -> dict[str, Any]:
    roles = raw.get("roles") or {}
    return {
        "id": str(raw.get("id", "")).strip().lower(),
        "ha_user": str(raw.get("ha_user", "")).strip(),
        "label": str(raw.get("label", "")).strip(),
        "email": str(raw.get("email", "")).strip(),
        "email_enabled": bool(raw.get("email_enabled", False)),
        "push_target": str(raw.get("push_target", "")).strip(),
        "push_enabled": bool(raw.get("push_enabled", False)),
        "roles": {role: bool(roles.get(role, False)) for role in ROLES},
    }


async def async_load_users(hass: HomeAssistant) -> dict[str, dict[str, Any]]:
    path = _config_path(hass)
    if not path.exists():
        return {}

    def _load() -> dict[str, dict[str, Any]]:
        data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        users: dict[str, dict[str, Any]] = {}
        for raw in data.get("users", []) or []:
            if not isinstance(raw, dict):
                continue
            user = _normalise_user(raw)
            if user["id"]:
                users[user["id"]] = user
        return users

    return await hass.async_add_executor_job(_load)


async def async_save_users(hass: HomeAssistant, users: dict[str, dict[str, Any]]) -> None:
    path = _config_path(hass)

    def _save() -> None:
        serialised = {"users": []}
        for user_id in sorted(users):
            user = users[user_id]
            serialised["users"].append(
                {
                    "id": user_id,
                    "ha_user": user.get("ha_user", ""),
                    "label": user.get("label", ""),
                    "email": user.get("email", ""),
                    "email_enabled": bool(user.get("email_enabled", False)),
                    "push_target": user.get("push_target", ""),
                    "push_enabled": bool(user.get("push_enabled", False)),
                    "roles": {role: bool((user.get("roles") or {}).get(role, False)) for role in ROLES},
                }
            )
        path.write_text(yaml.safe_dump(serialised, sort_keys=False, allow_unicode=False), encoding="utf-8")

    await hass.async_add_executor_job(_save)
