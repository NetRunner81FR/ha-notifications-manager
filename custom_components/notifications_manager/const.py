DOMAIN = "notifications_manager"
CONF_FILE = "notifications_users.yaml"
ENTITY_PREFIX = "notif"

PLATFORMS = ["switch", "text"]

ROLES = ["admin", "proprietaire", "resident", "utilisateur"]

TEXT_FIELDS = {
    "label": {"suffix": "label", "max": 64},
    "email": {"suffix": "email", "max": 128},
    "push_target": {"suffix": "push_target", "max": 128},
}

SWITCH_FIELDS = {
    "email_enabled": {"suffix": "email_enabled"},
    "push_enabled": {"suffix": "push_enabled"},
    "role_admin": {"suffix": "role_admin"},
    "role_proprietaire": {"suffix": "role_proprietaire"},
    "role_resident": {"suffix": "role_resident"},
    "role_utilisateur": {"suffix": "role_utilisateur"},
}
