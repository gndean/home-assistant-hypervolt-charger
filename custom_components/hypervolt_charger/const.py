"""Constants for the Hypervolt Charger integration."""

DOMAIN = "hypervolt_charger"

CONF_USERNAME = "username"
CONF_PASSWORD = "password"
CONF_CHARGER_ID = "charger_id"

# Options
CONF_ENABLE_STALENESS_DETECTION = "enable_staleness_detection"
CONF_API_VERSION_OVERRIDE = "api_version_override"
CONF_RESOLVED_API_VERSION = "resolved_api_version"

API_VERSION_AUTO = "auto"
API_VERSION_V2 = "v2"
API_VERSION_V3 = "v3"

# Charger "features" flag indicating Battery Safe (super_eco_battery_safe) support
FEATURE_BATTERY_SAFE = "home-battery-drain-prevention"
