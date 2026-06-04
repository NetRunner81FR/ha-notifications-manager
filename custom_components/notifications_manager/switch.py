from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN, ENTITY_PREFIX, ROLES, SWITCH_FIELDS


def _field_value(user: dict[str, Any], field: str) -> bool:
    if field.startswith("role_"):
        return bool((user.get("roles") or {}).get(field.replace("role_", "", 1), False))
    return bool(user.get(field, False))


class NotificationSwitch(SwitchEntity, RestoreEntity):
    def __init__(self, manager, user_id: str, user: dict[str, Any], field: str, suffix: str) -> None:
        self.manager = manager
        self.user_id = user_id
        self.field = field
        self.entity_key = f"switch:{user_id}:{field}"
        label = user.get("label") or user_id

        self._attr_unique_id = f"{DOMAIN}_{user_id}_{suffix}"
        self.entity_id = f"switch.{ENTITY_PREFIX}_{user_id}_{suffix}"
        self._attr_name = f"Notifs {label} - {suffix.replace('_', ' ').title()}"
        self._attr_icon = "mdi:account-check" if field.startswith("role_") else "mdi:toggle-switch"
        self._is_on = _field_value(user, field)

    @property
    def is_on(self) -> bool:
        return self._is_on

    async def async_added_to_hass(self) -> None:
        if (state := await self.async_get_last_state()) is not None and state.state in ("on", "off"):
            self._is_on = state.state == "on"
            await self.manager.async_set_value(self.user_id, self.field, self._is_on)

    async def async_turn_on(self, **kwargs: Any) -> None:
        self._is_on = True
        await self.manager.async_set_value(self.user_id, self.field, True)
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._is_on = False
        await self.manager.async_set_value(self.user_id, self.field, False)
        self.async_write_ha_state()


def build_switch_entities(manager, user_id: str, user: dict[str, Any]) -> list[NotificationSwitch]:
    return [
        NotificationSwitch(manager, user_id, user, field, meta["suffix"])
        for field, meta in SWITCH_FIELDS.items()
    ]


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    manager = hass.data[DOMAIN]
    await manager.async_register_platform("switch", async_add_entities)
