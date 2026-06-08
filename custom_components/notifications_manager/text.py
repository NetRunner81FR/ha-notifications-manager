"""Entites Text pour les champs texte de profil notification."""
from __future__ import annotations

import logging

from homeassistant.components.text import TextEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN, ENTITY_PREFIX

_LOGGER = logging.getLogger(__name__)

TEXT_ATTRIBUTES = {
    "label":       {"max": 64,  "name_suffix": "Libelle"},
    "email":       {"max": 128, "name_suffix": "Email"},
    "push_target": {"max": 128, "name_suffix": "Service push"},
}


async def async_setup_platform(hass: HomeAssistant, config, async_add_entities: AddEntitiesCallback, discovery_info=None):
    if DOMAIN not in hass.data:
        return

    domain_data = hass.data[DOMAIN]
    domain_data["text_add_entities"] = async_add_entities

    entities = _build_text_entities(domain_data["config"], domain_data)
    async_add_entities(entities, True)


def _build_text_entities(config: dict, domain_data: dict) -> list:
    entities = []
    for user in config.get("users", []):
        uid = user["id"]
        for attr, meta in TEXT_ATTRIBUTES.items():
            ent = NotifText(
                uid, attr,
                f"Notifs {user['label']} - {meta['name_suffix']}",
                user.get(attr, ""),
                meta["max"],
                domain_data,
            )
            entities.append(ent)
            domain_data.setdefault("entities", {}).setdefault(uid, {})[attr] = ent
    return entities


class NotifText(TextEntity, RestoreEntity):
    """Entite Text representant un champ texte de profil notification."""

    _attr_should_poll = False

    def __init__(self, user_id: str, attribute: str, name: str, initial: str, max_length: int, domain_data: dict):
        self._user_id = user_id
        self._attribute = attribute
        self._attr_name = name
        self._attr_unique_id = f"{DOMAIN}_{user_id}_{attribute}"
        self._value = initial
        self._attr_native_max = max_length
        self._attr_native_min = 0
        self._domain_data = domain_data
        self.entity_id = f"text.{ENTITY_PREFIX}_{user_id}_{attribute}"

    @property
    def native_value(self) -> str:
        return self._value

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None and last.state not in ("unknown", "unavailable"):
            self._value = last.state

    async def async_set_value(self, value: str) -> None:
        self._value = value
        self._persist()
        self.async_write_ha_state()

    def set_value(self, value: str) -> None:
        """Mise a jour sans persistance (appele par les services)."""
        self._value = value
        self.async_write_ha_state()

    def _persist(self) -> None:
        from .config_loader import load_config, save_config
        config = load_config()
        for user in config.get("users", []):
            if user["id"] == self._user_id:
                user[self._attribute] = self._value
        save_config(config)
