"""Entites Switch pour les booleans de notification (canaux, roles, SMTP global)."""
from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DOMAIN, ENTITY_PREFIX, ROLES

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass: HomeAssistant, config, async_add_entities: AddEntitiesCallback, discovery_info=None):
    """Configure les entites switch a partir de la config chargee."""
    if DOMAIN not in hass.data:
        return

    domain_data = hass.data[DOMAIN]
    domain_data["switch_add_entities"] = async_add_entities

    smtp_sw = SmtpSwitch()
    domain_data["smtp_switch"] = smtp_sw

    user_entities = _build_switch_entities(domain_data["config"], domain_data)
    async_add_entities([smtp_sw] + user_entities, True)


def _build_switch_entities(config: dict, domain_data: dict) -> list:
    entities = []
    for user in config.get("users", []):
        uid = user["id"]
        roles = user.get("roles", {})

        email_sw = NotifSwitch(
            uid, "email_enabled", f"Notifs {user['label']} - Email actif",
            user.get("email_enabled", False), domain_data,
        )
        push_sw = NotifSwitch(
            uid, "push_enabled", f"Notifs {user['label']} - Push actif",
            user.get("push_enabled", False), domain_data,
        )
        entities += [email_sw, push_sw]

        for role in ROLES:
            entities.append(NotifSwitch(
                uid, f"role_{role}", f"Notifs {user['label']} - Role {role}",
                roles.get(role, False), domain_data,
            ))

        domain_data.setdefault("entities", {}).setdefault(uid, {})
        domain_data["entities"][uid]["email_enabled"] = email_sw
        domain_data["entities"][uid]["push_enabled"] = push_sw
        for role in ROLES:
            domain_data["entities"][uid][f"role_{role}"] = entities[-len(ROLES) + ROLES.index(role)]

    return entities


class SmtpSwitch(SwitchEntity, RestoreEntity):
    """Switch representant l'activation globale du canal email (SMTP)."""

    _attr_should_poll = False
    _attr_name = "Notifications - SMTP actif"
    _attr_unique_id = f"{DOMAIN}_smtp_active"
    _attr_icon = "mdi:email-check-outline"
    entity_id = "switch.notifications_manager_smtp_active"

    def __init__(self) -> None:
        self._state = False

    @property
    def is_on(self) -> bool:
        return self._state

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None:
            self._state = last.state == "on"

    async def async_turn_on(self, **kwargs) -> None:
        self._state = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        self._state = False
        self.async_write_ha_state()


class NotifSwitch(SwitchEntity, RestoreEntity):
    """Switch HA representant un boolean de profil notification."""

    _attr_should_poll = False

    def __init__(self, user_id: str, attribute: str, name: str, initial: bool, domain_data: dict):
        self._user_id = user_id
        self._attribute = attribute
        self._attr_name = name
        self._attr_unique_id = f"{DOMAIN}_{user_id}_{attribute}"
        self._state = initial
        self._domain_data = domain_data
        self.entity_id = f"switch.{ENTITY_PREFIX}_{user_id}_{attribute}"

    @property
    def is_on(self) -> bool:
        return self._state

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is not None:
            self._state = last.state == "on"

    async def async_turn_on(self, **kwargs) -> None:
        self._state = True
        self._persist()
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        self._state = False
        self._persist()
        self.async_write_ha_state()

    def set_state(self, value: bool) -> None:
        """Mise a jour sans persistance (appele par les services)."""
        self._state = value
        self.async_write_ha_state()

    def _persist(self) -> None:
        from .config_loader import load_config, save_config, CONFIG_FILE
        config = load_config()
        for user in config.get("users", []):
            if user["id"] != self._user_id:
                continue
            if self._attribute in ("email_enabled", "push_enabled"):
                user[self._attribute] = self._state
            elif self._attribute.startswith("role_"):
                role = self._attribute[len("role_"):]
                user.setdefault("roles", {})[role] = self._state
        save_config(config)
