"""Constants for the CapybaraVPN integration."""

DOMAIN = "capybaravpn"
PLATFORMS = ["sensor", "binary_sensor"]

BASE_URL = "https://capybaravpn.app"

CONF_SCAN_INTERVAL = "scan_interval_minutes"
DEFAULT_SCAN_INTERVAL_MINUTES = 60
MIN_SCAN_INTERVAL_MINUTES = 5
MAX_SCAN_INTERVAL_MINUTES = 1440
