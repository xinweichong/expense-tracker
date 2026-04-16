import os
from pathlib import Path
from typing import Any

import yaml


DEFAULTS = {
    "server": {"host": "0.0.0.0", "port": 8080, "webhook_base_url": "http://localhost:8080"},
    "gmail": {"poll_interval_seconds": 120, "sender_filters": []},
}


def load_config(config_path: str) -> dict[str, Any]:
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {config_path}")

    with open(path) as f:
        config = yaml.safe_load(f) or {}

    # Apply defaults for missing sections
    for section, defaults in DEFAULTS.items():
        if section not in config:
            config[section] = {}
        for key, default_val in defaults.items():
            config[section].setdefault(key, default_val)

    # Environment variable overrides
    if token := os.environ.get("TELEGRAM_BOT_TOKEN"):
        config.setdefault("telegram", {})["bot_token"] = token
    if password_hash := os.environ.get("WEB_PASSWORD_HASH"):
        config.setdefault("web", {})["password_hash"] = password_hash

    return config
