"""Constants for the Synology Download Station integration."""

from __future__ import annotations

from homeassistant.const import Platform

DOMAIN = "synology_download_station"
PLATFORMS = [Platform.SENSOR, Platform.TEXT]

DEFAULT_PORT = 5001
DEFAULT_USE_SSL = True
DEFAULT_VERIFY_SSL = False
DEFAULT_SCAN_INTERVAL = 10

CONF_SCAN_INTERVAL = "scan_interval"

SERVICE_ADD_TASK = "add_task"
SERVICE_ADD_TORRENT = "add_torrent"
ATTR_URL = "url"
ATTR_DESTINATION = "destination"
ATTR_CONFIG_ENTRY_ID = "config_entry_id"
ATTR_TORRENT = "torrent"
ATTR_FILE_PATH = "file_path"
ATTR_FILENAME = "filename"

CARD_URL = f"/{DOMAIN}/card.js"
