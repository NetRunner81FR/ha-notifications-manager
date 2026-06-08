# Changelog

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
