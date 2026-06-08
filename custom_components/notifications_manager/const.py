DOMAIN = "notifications_manager"

CONFIG_FILE = "/config/notifications_users.yaml"

ROLES = ["admin", "proprietaire", "resident", "utilisateur"]

# Prefixe commun pour toutes les entites du module
ENTITY_PREFIX = "notif"

# Acces par role module (independant du role HA admin)
ROLES_WRITE = {"admin"}
ROLES_READ = {"admin", "proprietaire"}
