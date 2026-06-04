# Home Assistant Notifications Manager

Standalone HACS integration for managing notification recipients as native Home
Assistant entities.

Repository target:

```text
NetRunner81FR/ha-notifications-manager
```

HACS type:

```text
Integration
```

## What it provides

For each user declared in `/config/notifications_users.yaml`, the integration
creates:

- `switch.notif_<id>_email_enabled`
- `switch.notif_<id>_push_enabled`
- `switch.notif_<id>_role_admin`
- `switch.notif_<id>_role_proprietaire`
- `switch.notif_<id>_role_resident`
- `switch.notif_<id>_role_utilisateur`
- `text.notif_<id>_label`
- `text.notif_<id>_email`
- `text.notif_<id>_push_target`

The integration does not send notifications by itself. Notification transport
remains a Home Assistant responsibility, typically through the example
`script.notify_transverse` package.

## Installation with HACS

1. Add this repository as a custom repository in HACS.
2. Select category `Integration`.
3. Install `Notifications Manager`.
4. Restart Home Assistant.
5. Add the YAML activation below to `configuration.yaml`.

```yaml
notifications_manager:
```

6. Copy `examples/notifications_users.yaml` to:

```text
/config/notifications_users.yaml
```

7. Restart Home Assistant or call:

```yaml
service: notifications_manager.reload
```

## Example package

Copy `examples/notify_transverse.yaml` into your packages directory, for
example:

```text
/config/packages/notify_transverse.yaml
```

Then call:

```yaml
service: script.notify_transverse
data:
  title: "Test notification"
  message: "Hello"
  category: "info"
  roles:
    - admin
```

`tiers` is accepted by the example package as a legacy alias for `roles`.

## Services

- `notifications_manager.add_user`
- `notifications_manager.update_user`
- `notifications_manager.remove_user`
- `notifications_manager.reload`

## Security notes

- Do not commit real email addresses unless they are intentionally public.
- Do not commit SMTP credentials.
- Do not commit mobile_app targets that identify private devices unless this is
  intentional.
- This integration does not use MQTT.
- This integration does not call equipment control services.

## Factory compatibility

If you also use `homeassistant-factory`, ensure deployment scripts do not
overwrite `custom_components/notifications_manager/` in environments where HACS
manages this integration.
