import json
import logging
import os

logger = logging.getLogger(__name__)


def load_settings(plugin_key, defaults=None):
    path = _get_config_path()
    if not path:
        return defaults or {}
    try:
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                return json.load(f).get(plugin_key, defaults or {})
    except Exception:  # noqa: BLE001
        logger.debug("Error loading settings for %s", plugin_key)
    return defaults or {}


def save_settings(plugin_key, settings):
    path = _get_config_path()
    if not path:
        return
    try:
        data = {}
        if os.path.exists(path):
            with open(path, encoding="utf-8") as f:
                data = json.load(f)
        data[plugin_key] = settings
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
    except Exception:
        logger.exception("Error saving settings for %s", plugin_key)


def _get_config_path():
    return "plugins_config.json"
