from __future__ import annotations

import logging
from typing import Any, Callable

import voluptuous as vol

from homeassistant.const import CONF_ID
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import discovery
import homeassistant.helpers.config_validation as cv

from .config_loader import async_load_users, async_save_users
from .const import DOMAIN, PLATFORMS, ROLES

_LOGGER = logging.getLogger(__name__)

ROLE_SCHEMA = vol.Schema({vol.Optional(role, default=False): cv.boolean for role in ROLES})

ADD_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ID): cv.string,
        vol.Optional("ha_user", default=""): cv.string,
        vol.Optional("label", default=""): cv.string,
        vol.Optional("email", default=""): cv.string,
        vol.Optional("email_enabled", default=False): cv.boolean,
        vol.Optional("push_target", default=""): cv.string,
        vol.Optional("push_enabled", default=False): cv.boolean,
        vol.Optional("roles", default={}): ROLE_SCHEMA,
    }
)
UPDATE_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_ID): cv.string,
        vol.Optional("ha_user"): cv.string,
        vol.Optional("label"): cv.string,
        vol.Optional("email"): cv.string,
        vol.Optional("email_enabled"): cv.boolean,
        vol.Optional("push_target"): cv.string,
        vol.Optional("push_enabled"): cv.boolean,
        vol.Optional("roles"): ROLE_SCHEMA,
    }
)
REMOVE_USER_SCHEMA = vol.Schema({vol.Required(CONF_ID): cv.string})


def _normalise_id(user_id: str) -> str:
    return str(user_id).strip().lower().replace(" ", "_")


def _default_user(user_id: str) -> dict[str, Any]:
    return {
        "id": user_id,
        "ha_user": "",
        "label": user_id,
        "email": "",
        "email_enabled": False,
        "push_target": "",
        "push_enabled": False,
        "roles": {role: False for role in ROLES},
    }


class NotificationsManager:
    def __init__(self, hass: HomeAssistant, users: dict[str, dict[str, Any]]) -> None:
        self.hass = hass
        self.users = users
        self._platform_callbacks: dict[str, Callable[[list[Any]], None]] = {}
        self.entities_by_user: dict[str, list[Any]] = {}

    async def async_register_platform(self, platform: str, add_entities: Callable[[list[Any]], None]) -> None:
        self._platform_callbacks[platform] = add_entities
        await self.async_add_missing_entities(platform)

    async def async_add_missing_entities(self, platform: str | None = None) -> None:
        platforms = [platform] if platform else list(self._platform_callbacks)
        for user_id, user in self.users.items():
            for current_platform in platforms:
                callback = self._platform_callbacks.get(current_platform)
                if not callback:
                    continue
                entities = self._create_entities(current_platform, user_id, user)
                if entities:
                    self.entities_by_user.setdefault(user_id, []).extend(entities)
                    callback(entities)

    def _create_entities(self, platform: str, user_id: str, user: dict[str, Any]) -> list[Any]:
        existing = {
            getattr(entity, "entity_key", None)
            for entity in self.entities_by_user.get(user_id, [])
        }
        if platform == "switch":
            from .switch import build_switch_entities

            return [entity for entity in build_switch_entities(self, user_id, user) if entity.entity_key not in existing]
        if platform == "text":
            from .text import build_text_entities

            return [entity for entity in build_text_entities(self, user_id, user) if entity.entity_key not in existing]
        return []

    async def async_set_value(self, user_id: str, field: str, value: Any) -> None:
        user = self.users.setdefault(user_id, _default_user(user_id))
        if field.startswith("role_"):
            role = field.replace("role_", "", 1)
            user.setdefault("roles", {})[role] = bool(value)
        else:
            user[field] = value

    async def async_add_or_update_user(self, data: dict[str, Any], persist: bool = True) -> None:
        user_id = _normalise_id(data[CONF_ID])
        user = self.users.setdefault(user_id, _default_user(user_id))
        for key, value in data.items():
            if key == CONF_ID:
                continue
            if key == "roles":
                user.setdefault("roles", {}).update({role: bool(value.get(role, False)) for role in ROLES})
            else:
                user[key] = value
        if persist:
            await async_save_users(self.hass, self.users)
        await self.async_add_missing_entities()

    async def async_remove_user(self, user_id: str) -> None:
        user_id = _normalise_id(user_id)
        self.users.pop(user_id, None)
        await async_save_users(self.hass, self.users)
        for entity in self.entities_by_user.pop(user_id, []):
            await entity.async_remove()

    async def async_reload(self) -> None:
        self.users = await async_load_users(self.hass)
        await self.async_add_missing_entities()


async def async_setup(hass: HomeAssistant, config: dict[str, Any]) -> bool:
    users = await async_load_users(hass)
    manager = NotificationsManager(hass, users)
    hass.data[DOMAIN] = manager

    async def _add_user(call: ServiceCall) -> None:
        await manager.async_add_or_update_user(dict(call.data))

    async def _update_user(call: ServiceCall) -> None:
        await manager.async_add_or_update_user(dict(call.data))

    async def _remove_user(call: ServiceCall) -> None:
        await manager.async_remove_user(call.data[CONF_ID])

    async def _reload(call: ServiceCall) -> None:
        await manager.async_reload()

    hass.services.async_register(DOMAIN, "add_user", _add_user, schema=ADD_USER_SCHEMA)
    hass.services.async_register(DOMAIN, "update_user", _update_user, schema=UPDATE_USER_SCHEMA)
    hass.services.async_register(DOMAIN, "remove_user", _remove_user, schema=REMOVE_USER_SCHEMA)
    hass.services.async_register(DOMAIN, "reload", _reload)

    for platform in PLATFORMS:
        hass.async_create_task(discovery.async_load_platform(hass, platform, DOMAIN, {}, config))

    _LOGGER.info("Notifications Manager loaded with %s user(s)", len(users))
    return True
