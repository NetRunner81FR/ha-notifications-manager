"""Lecture et ecriture du fichier notifications_users.yaml."""
import logging
import os

import voluptuous as vol
import yaml

from .const import CONFIG_FILE, ROLES

_LOGGER = logging.getLogger(__name__)

USER_SCHEMA = vol.Schema({
    vol.Required("id"): str,
    vol.Optional("ha_user"): str,
    vol.Required("label"): str,
    vol.Optional("email", default=""): str,
    vol.Optional("email_enabled", default=False): bool,
    vol.Optional("push_target", default=""): str,
    vol.Optional("push_enabled", default=False): bool,
    vol.Required("roles"): {
        vol.Optional("admin", default=False): bool,
        vol.Optional("proprietaire", default=False): bool,
        vol.Optional("resident", default=False): bool,
        vol.Optional("utilisateur", default=False): bool,
    },
})

CONFIG_SCHEMA = vol.Schema({
    vol.Optional("version", default=1): int,
    vol.Optional("roles_available", default=ROLES): list,
    vol.Optional("users", default=[]): [USER_SCHEMA],
})


def load_config(path: str = CONFIG_FILE) -> dict:
    """Charge et valide le fichier de configuration."""
    if not os.path.exists(path):
        _LOGGER.warning("notifications_manager: %s absent, demarrage avec config vide", path)
        return {"version": 1, "users": []}

    try:
        with open(path, encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
        return CONFIG_SCHEMA(raw)
    except (yaml.YAMLError, vol.Invalid) as err:
        _LOGGER.error("notifications_manager: config invalide dans %s : %s", path, err)
        return {"version": 1, "users": []}


def save_config(config: dict, path: str = CONFIG_FILE) -> None:
    """Persiste la configuration dans le fichier YAML."""
    try:
        with open(path, "w", encoding="utf-8") as f:
            yaml.dump(config, f, allow_unicode=True, default_flow_style=False, sort_keys=False)
    except OSError as err:
        _LOGGER.error("notifications_manager: impossible d'ecrire %s : %s", path, err)


def find_user(config: dict, user_id: str) -> dict | None:
    return next((u for u in config.get("users", []) if u["id"] == user_id), None)


def validate_user_id(user_id: str) -> bool:
    """Verifie que l'id est un slug ASCII valide."""
    import re
    return bool(re.match(r"^[a-z0-9_]+$", user_id))
