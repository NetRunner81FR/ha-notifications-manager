"""Integration notifications_manager — gestion dynamique des profils notification HA."""
from __future__ import annotations

import ast
import json
import logging
from pathlib import Path

# Read manifest at import time (synchronous, before event loop) to avoid
# blocking I/O inside async context (HA util.loop warning).
try:
    _MANIFEST_VERSION: str = json.loads(
        (Path(__file__).parent / "manifest.json").read_text(encoding="utf-8")
    )["version"]
except Exception:
    _MANIFEST_VERSION = "0"

import voluptuous as vol
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import discovery
from homeassistant.helpers.typing import ConfigType

from .config_loader import (
    CONFIG_FILE,
    find_user,
    load_config,
    load_modules_config,
    save_config,
    validate_user_id,
)
from .const import DOMAIN, ROLES

_LOGGER = logging.getLogger(__name__)

PLATFORMS = [Platform.SWITCH, Platform.TEXT]

CONFIG_SCHEMA = vol.Schema({DOMAIN: vol.Schema({})}, extra=vol.ALLOW_EXTRA)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Point d'entree YAML : charge la config et enregistre les services."""
    cfg = await hass.async_add_executor_job(load_config)
    modules = await hass.async_add_executor_job(load_modules_config)
    hass.data[DOMAIN] = {
        "config": cfg,
        "modules": modules,
        "entities": {},
        "switch_add_entities": None,
        "text_add_entities": None,
    }

    for platform in PLATFORMS:
        discovery.load_platform(hass, platform, DOMAIN, {}, config)

    _register_services(hass)
    await _register_static_path(hass)
    _register_panel(hass)
    _register_api_views(hass)

    _LOGGER.info(
        "notifications_manager: %d utilisateur(s), %d modules core, %d subscribers",
        len(cfg.get("users", [])),
        len(modules.get("core", [])),
        len(modules.get("subscribers", [])),
    )
    return True


async def _register_static_path(hass: HomeAssistant) -> None:
    www_path = Path(__file__).parent / "www"
    if not www_path.is_dir():
        _LOGGER.warning("notifications_manager: dossier www/ absent, panel JS non servi")
        return
    try:
        from homeassistant.components.http import StaticPathConfig
        await hass.http.async_register_static_paths([
            StaticPathConfig("/local/notifications_manager", str(www_path), False)
        ])
        _LOGGER.info("notifications_manager: static path /local/notifications_manager -> %s", www_path)
    except Exception as exc:
        _LOGGER.error("notifications_manager: erreur enregistrement static path: %s", exc)


def _register_api_views(hass: HomeAssistant) -> None:
    from homeassistant.components.http import HomeAssistantView

    class NotificationsModulesView(HomeAssistantView):
        url = "/api/notifications_manager/modules"
        name = "api:notifications_manager:modules"
        requires_auth = True

        async def get(self, request):
            modules = hass.data.get(DOMAIN, {}).get("modules", {"core": [], "subscribers": []})
            return self.json(modules)

    hass.http.register_view(NotificationsModulesView())


def _register_panel(hass: HomeAssistant) -> None:
    try:
        from homeassistant.components.frontend import async_register_built_in_panel
        url = f"/local/notifications_manager/notifications-supervision-panel.js?v={_MANIFEST_VERSION}"
        async_register_built_in_panel(
            hass,
            "custom",
            sidebar_title="Notifications",
            sidebar_icon="mdi:bell-check-outline",
            frontend_url_path="notifications-manager",
            config={
                "_panel_custom": {
                    "module_url": url,
                    "name": "notifications-supervision-panel",
                    "embed_iframe": False,
                    "trust_external": False,
                }
            },
            require_admin=False,
        )
        _LOGGER.info("notifications_manager: panel supervision enregistre -> %s", url)
    except Exception as exc:
        _LOGGER.error("notifications_manager: erreur enregistrement panel: %s", exc)


def _is_entity_on(hass: HomeAssistant, entity_id: str) -> bool:
    state = hass.states.get(entity_id)
    return state is not None and state.state == "on"


def _state_value(hass: HomeAssistant, entity_id: str) -> str:
    state = hass.states.get(entity_id)
    if state is None:
        return ""
    v = state.state
    return "" if v in ("unknown", "unavailable", "none") else v


def _resolve_module_roles(hass: HomeAssistant, module: str) -> list[str] | None:
    """Resout les roles a partir des helpers d'un module. None si module non autorise ou helpers absents."""
    declared = hass.data.get(DOMAIN, {}).get("modules", {})
    all_modules = declared.get("core", []) + declared.get("subscribers", [])
    if module not in all_modules:
        _LOGGER.warning(
            "notifications_manager: module '%s' non declare dans notifications_modules.yaml"
            " — notification ignoree. Ajouter le module dans subscribers pour l'activer.",
            module,
        )
        return None
    level_entity = f"input_select.{module}_notification_level"
    admin_entity = f"input_boolean.{module}_notif_admin"
    if hass.states.get(level_entity) is None:
        _LOGGER.warning(
            "notifications_manager: module '%s' fourni mais %s absent — notification ignoree",
            module, level_entity,
        )
        return None
    level = _state_value(hass, level_entity)
    roles: list[str] = []
    if _is_entity_on(hass, admin_entity):
        roles.append("admin")
    # Cascade vers le haut : un niveau cible les utilisateurs de ce niveau ET au-dessus.
    # proprietaire > resident > utilisateur
    # level=utilisateur  -> tous les roles recoivent (lowest)
    # level=resident     -> resident et proprietaire seulement
    # level=proprietaire -> proprietaire seulement (highest)
    if level == "utilisateur":
        roles += ["proprietaire", "resident", "utilisateur"]
    elif level == "resident":
        roles += ["proprietaire", "resident"]
    elif level == "proprietaire":
        roles += ["proprietaire"]
    return roles


def _parse_roles(roles_raw) -> list[str]:
    """Parse roles depuis liste Python ou chaine Jinja (ex. \"['admin', 'resident']\")."""
    if isinstance(roles_raw, list):
        return [str(r).strip() for r in roles_raw if r]
    if isinstance(roles_raw, str):
        try:
            parsed = ast.literal_eval(roles_raw)
            if isinstance(parsed, list):
                return [str(r).strip() for r in parsed if r]
        except Exception:
            pass
        return [
            r.strip().strip("'\"")
            for r in roles_raw.strip("[]").split(",")
            if r.strip().strip("'\"")
        ]
    return []


def _register_services(hass: HomeAssistant) -> None:

    async def handle_notify(call: ServiceCall) -> None:
        title = call.data.get("title", "")
        message = call.data.get("message", "")
        category = call.data.get("category", "info")
        dry_run = bool(call.data.get("dry_run", False))
        module = call.data.get("module", "")

        roles_raw = call.data.get("roles", [])
        if roles_raw:
            roles = _parse_roles(roles_raw)
        elif module:
            resolved = _resolve_module_roles(hass, module)
            if resolved is None:
                return
            roles = resolved
        else:
            roles = []

        if not roles:
            _LOGGER.info(
                "notifications_manager.notify: aucun role actif (module=%s category=%s), notification ignoree",
                module or "—", category,
            )
            return

        env = _state_value(hass, "input_text.ha_environment_label").strip()
        effective_title = f"[{env}] {title}" if env else title

        slugs = [
            s.entity_id[len("text.notif_"):-len("_label")]
            for s in hass.states.async_all("text")
            if s.entity_id.startswith("text.notif_") and s.entity_id.endswith("_label")
        ]

        smtp_on = _is_entity_on(hass, "switch.notifications_manager_smtp_active")

        if dry_run:
            _LOGGER.info(
                "notifications_manager.notify [dry_run]: title='%s' category='%s' roles=%s slugs=%s",
                title, category, roles, slugs,
            )
            return

        sent_emails: set[str] = set()
        sent_push_targets: set[str] = set()

        for slug in slugs:
            role_match = any(_is_entity_on(hass, f"switch.notif_{slug}_role_{r}") for r in roles)
            if not role_match:
                continue

            push_target = _state_value(hass, f"text.notif_{slug}_push_target").strip()
            if _is_entity_on(hass, f"switch.notif_{slug}_push_enabled") and push_target:
                if push_target not in sent_push_targets:
                    sent_push_targets.add(push_target)
                    try:
                        domain_svc, svc_name = push_target.rsplit(".", 1)
                        await hass.services.async_call(
                            domain_svc, svc_name,
                            {"title": effective_title, "message": message},
                            blocking=False,
                        )
                    except Exception as exc:
                        _LOGGER.warning("notifications_manager.notify: erreur push %s: %s", push_target, exc)

            email = _state_value(hass, f"text.notif_{slug}_email").strip()
            if smtp_on and _is_entity_on(hass, f"switch.notif_{slug}_email_enabled") and email:
                if email not in sent_emails:
                    sent_emails.add(email)
                    try:
                        await hass.services.async_call(
                            "notify", "notify_smtp",
                            {"title": effective_title, "message": message, "target": email},
                            blocking=False,
                        )
                    except Exception as exc:
                        _LOGGER.warning("notifications_manager.notify: erreur email %s: %s", email, exc)

    async def handle_add_user(call: ServiceCall) -> None:
        uid = call.data["id"]
        if not validate_user_id(uid):
            _LOGGER.error("notifications_manager.add_user: id invalide '%s'", uid)
            return

        cfg = await hass.async_add_executor_job(load_config)
        if find_user(cfg, uid):
            _LOGGER.error("notifications_manager.add_user: id '%s' deja existant", uid)
            return

        roles_raw = call.data.get("roles") or {}
        roles = {r: bool(roles_raw.get(r, False)) for r in ROLES}

        new_user = {
            "id": uid,
            "label": call.data["label"],
            "email": call.data.get("email", ""),
            "email_enabled": call.data.get("email_enabled", False),
            "push_target": call.data.get("push_target", ""),
            "push_enabled": call.data.get("push_enabled", False),
            "roles": roles,
        }
        if "ha_user" in call.data:
            new_user["ha_user"] = call.data["ha_user"]

        cfg["users"].append(new_user)
        await hass.async_add_executor_job(save_config, cfg)
        hass.data[DOMAIN]["config"] = cfg
        await _add_user_entities(hass, new_user)
        _LOGGER.info("notifications_manager: utilisateur '%s' ajoute", uid)

    async def handle_update_user(call: ServiceCall) -> None:
        uid = call.data["id"]
        cfg = await hass.async_add_executor_job(load_config)
        user = find_user(cfg, uid)
        if not user:
            _LOGGER.error("notifications_manager.update_user: '%s' introuvable", uid)
            return

        for field in ("label", "email", "email_enabled", "push_target", "push_enabled", "ha_user"):
            if field in call.data:
                user[field] = call.data[field]

        if "roles" in call.data:
            roles_raw = call.data["roles"] or {}
            user["roles"] = {r: bool(roles_raw.get(r, False)) for r in ROLES}

        await hass.async_add_executor_job(save_config, cfg)
        hass.data[DOMAIN]["config"] = cfg
        await _sync_user_entities(hass, user)
        _LOGGER.info("notifications_manager: utilisateur '%s' mis a jour", uid)

    async def handle_remove_user(call: ServiceCall) -> None:
        uid = call.data["id"]
        cfg = await hass.async_add_executor_job(load_config)
        user = find_user(cfg, uid)
        if not user:
            _LOGGER.error("notifications_manager.remove_user: '%s' introuvable", uid)
            return

        cfg["users"] = [u for u in cfg["users"] if u["id"] != uid]
        await hass.async_add_executor_job(save_config, cfg)
        hass.data[DOMAIN]["config"] = cfg
        await _remove_user_entities(hass, uid)
        _LOGGER.info("notifications_manager: utilisateur '%s' supprime", uid)

    async def handle_reload(call: ServiceCall) -> None:
        cfg = await hass.async_add_executor_job(load_config)
        modules = await hass.async_add_executor_job(load_modules_config)
        hass.data[DOMAIN]["config"] = cfg
        hass.data[DOMAIN]["modules"] = modules
        _LOGGER.info(
            "notifications_manager: reload — %d utilisateur(s), %d modules core, %d subscribers",
            len(cfg.get("users", [])),
            len(modules.get("core", [])),
            len(modules.get("subscribers", [])),
        )

    hass.services.async_register(DOMAIN, "notify", handle_notify)
    hass.services.async_register(DOMAIN, "add_user", handle_add_user)
    hass.services.async_register(DOMAIN, "update_user", handle_update_user)
    hass.services.async_register(DOMAIN, "remove_user", handle_remove_user)
    hass.services.async_register(DOMAIN, "reload", handle_reload)


async def _add_user_entities(hass: HomeAssistant, user: dict) -> None:
    """Cree et enregistre les entites pour un nouvel utilisateur."""
    from .switch import NotifSwitch
    from .text import NotifText, TEXT_ATTRIBUTES

    domain_data = hass.data[DOMAIN]
    uid = user["id"]
    roles = user.get("roles", {})
    new_entities = []

    email_sw = NotifSwitch(uid, "email_enabled", f"Notifs {user['label']} - Email actif",
                           user.get("email_enabled", False), domain_data)
    push_sw = NotifSwitch(uid, "push_enabled", f"Notifs {user['label']} - Push actif",
                          user.get("push_enabled", False), domain_data)
    new_entities += [email_sw, push_sw]

    role_entities = {}
    for role in ROLES:
        sw = NotifSwitch(uid, f"role_{role}", f"Notifs {user['label']} - Role {role}",
                         roles.get(role, False), domain_data)
        new_entities.append(sw)
        role_entities[f"role_{role}"] = sw

    text_entities = {}
    for attr, meta in TEXT_ATTRIBUTES.items():
        ent = NotifText(uid, attr, f"Notifs {user['label']} - {meta['name_suffix']}",
                        user.get(attr, ""), meta["max"], domain_data)
        new_entities.append(ent)
        text_entities[attr] = ent

    domain_data["entities"][uid] = {
        "email_enabled": email_sw, "push_enabled": push_sw,
        **role_entities, **text_entities,
    }

    if domain_data["switch_add_entities"]:
        domain_data["switch_add_entities"]([email_sw, push_sw] + list(role_entities.values()), True)
    if domain_data["text_add_entities"]:
        domain_data["text_add_entities"](list(text_entities.values()), True)


async def _sync_user_entities(hass: HomeAssistant, user: dict) -> None:
    """Synchronise les etats des entites existantes apres update_user."""
    domain_data = hass.data[DOMAIN]
    uid = user["id"]
    ents = domain_data["entities"].get(uid, {})

    for attr in ("email_enabled", "push_enabled"):
        if attr in ents:
            ents[attr].set_state(user.get(attr, False))
    for role in ROLES:
        key = f"role_{role}"
        if key in ents:
            ents[key].set_state(user.get("roles", {}).get(role, False))
    for attr in ("label", "email", "push_target"):
        if attr in ents:
            ents[attr].set_value(user.get(attr, ""))


async def _remove_user_entities(hass: HomeAssistant, user_id: str) -> None:
    """Supprime les entites HA d'un utilisateur retire."""
    domain_data = hass.data[DOMAIN]
    ents = domain_data["entities"].pop(user_id, {})
    for entity in ents.values():
        await entity.async_remove()
