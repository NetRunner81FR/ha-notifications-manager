from __future__ import annotations

from typing import Any

from homeassistant.components.text import TextEntity
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN, ENTITY_PREFIX, TEXT_FIELDS


class NotificationText(TextEntity, RestoreEntity):
    def __init__(self, manager, user_id: str, user: dict[str, Any], field: str, suffix: str, max_chars: int) -> None:
        self.manager = manager
        self.user_id = user_id
        self.field = field
        self.entity_key = f"text:{user_id}:{field}"
        label = user.get("label") or user_id

        self._attr_unique_id = f"{DOMAIN}_{user_id}_{suffix}"
        self.entity_id = f"text.{ENTITY_PREFIX}_{user_id}_{suffix}"
        self._attr_name = f"Notifs {label} - {suffix.replace('_', ' ').title()}"
        self._attr_icon = "mdi:form-textbox"
        self._attr_native_max = max_chars
        self._value = str(user.get(field, "") or "")

    @property
    def native_value(self) -> str:
        return self._value

    async def async_added_to_hass(self) -> None:
        if (state := await self.async_get_last_state()) is not None:
            self._value = state.state if state.state not in ("unknown", "unavailable") else self._value
            await self.manager.async_set_value(self.user_id, self.field, self._value)

    async def async_set_value(self, value: str) -> None:
        self._value = value
        await self.manager.async_set_value(self.user_id, self.field, value)
        self.async_write_ha_state()


def build_text_entities(manager, user_id: str, user: dict[str, Any]) -> list[NotificationText]:
    return [
        NotificationText(manager, user_id, user, field, meta["suffix"], meta["max"])
        for field, meta in TEXT_FIELDS.items()
    ]


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    manager = hass.data[DOMAIN]
    await manager.async_register_platform("text", async_add_entities)
