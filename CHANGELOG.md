# Changelog

## 0.9.1-beta.1

- Fix UX: preserve focus on text inputs during HA state updates (`_isUserEditing()` guard on `set hass()`).
- Fix UX: preserve scroll position around all `innerHTML` rebuilds (`_saveScrollPosition` / `_restoreScrollPosition`).
- Affects: email field focus loss, scroll reset when editing params at bottom of page, admin/resident selector requiring two actions.

## 0.3.2

- Enforce `notifications_modules.yaml` as a true whitelist: calls to
  `notifications_manager.notify` with an undeclared `module:` are now rejected
  with a WARNING log and silently ignored. Previously, undeclared modules could
  still pass through if their HA helper entities happened to exist.
- Add documentation header in `notifications_modules.yaml` explaining the
  registry role, core vs. subscribers distinction, and how to add a new module
  without modifying Python code.
- Activate `veilleuses_axel` as a declared subscriber module.
- Bump component version to 0.3.2.

## 0.3.1-beta.1

- Fix cascade direction in `module:` routing: `level=proprietaire` now notifies
  only `proprietaire` users (highest privilege, fewest recipients); `level=resident`
  notifies `proprietaire` + `resident`; `level=utilisateur` notifies all three.
  Previous v0.3.0 had the cascade inverted (lower privilege = fewer recipients).
- Add email and push deduplication: a unique address/target is contacted at most
  once per notification, even if multiple user slugs resolve to the same address.
- Bump component version to 0.3.1.

## 0.3.0-beta.1

- Add `module:` field to `notifications_manager.notify` service: auto-resolves roles
  from `input_select.<module>_notification_level` + `input_boolean.<module>_notif_admin`.
  Backward-compatible: explicit `roles:` still takes priority.
- Add REST endpoint `GET /api/notifications_manager/modules` returning the
  core/subscribers taxonomy loaded from `/config/notifications_modules.yaml`.
- Add `load_modules_config()` in `config_loader.py` reading
  `/config/notifications_modules.yaml` at startup.
- Panel JS v0.9.0: add "Modules" tab showing core/subscriber taxonomy with
  current notification level and admin status per module.
- Bump component version to 0.3.0.

## 0.2.2-beta.1

- Add navigation bar at the top of the supervision panel with three buttons:
  Accueil, Supervision dashboard, Admin. Eliminates the need to use the browser
  back button to exit the panel.
- Panel JS bumped to v0.8.0.

## 0.2.1-beta.1

- Fix: read `manifest.json` at module import time instead of inside the async
  event loop, eliminating the `blocking call to read_text` warning logged by
  `homeassistant.util.loop` on every HA startup.

## 0.2.0-beta.1

- Add native service `notifications_manager.notify` with category and roles routing.
  Replaces the standalone `script.notify_transverse` YAML package.
- Add `switch.notifications_manager_smtp_active` entity exposed automatically at setup.
  Replaces the manual `input_boolean.notif_smtp_active` helper.
- Embed supervision frontend v2 as a built-in HA panel registered automatically at
  startup (no separate HACS plugin or Lovelace resource required).
- Panel served at `/notifications-manager` sidebar entry.
- Panel JS files served from the component `www/` directory via static path registration.
- Require Home Assistant 2024.6.0+ (async_register_static_paths API).

## 0.1.0

- Promote the standalone HACS integration to the first stable release.
- Keep the validated `0.1.0-beta.1` feature set unchanged.
- Confirm the integration is managed by HACS and can run alongside the factory
  deployment pipeline.

## 0.1.0-beta.1

- Initial standalone HACS integration staging.
- Add native switch and text entities for notification recipients.
- Add services `add_user`, `update_user`, `remove_user` and `reload`.
- Add YAML examples for `notifications_users.yaml`, `notify_transverse.yaml`,
  `configuration.yaml` and a reference dashboard.
