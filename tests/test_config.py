import pytest
import os
import yaml
from src.config import load_config


@pytest.fixture
def config_file(tmp_path):
    config = {
        "gmail": {
            "credentials_file": "creds.json",
            "poll_interval_seconds": 60,
            "sender_filters": ["test@example.com"],
        },
        "server": {"host": "127.0.0.1", "port": 9090, "webhook_base_url": "http://localhost"},
        "web": {"password_hash": "fakehash"},
        "telegram": {"bot_token": "default-token"},
        "categories": [
            {"name": "Food", "keywords": ["food"], "icon": "🍜"},
        ],
    }
    path = tmp_path / "config.yaml"
    with open(path, "w") as f:
        yaml.dump(config, f)
    return str(path)


class TestLoadConfig:
    def test_loads_from_file(self, config_file):
        config = load_config(config_file)
        assert config["gmail"]["poll_interval_seconds"] == 60
        assert config["telegram"]["bot_token"] == "default-token"

    def test_env_override_for_bot_token(self, config_file):
        os.environ["TELEGRAM_BOT_TOKEN"] = "env-token"
        try:
            config = load_config(config_file)
            assert config["telegram"]["bot_token"] == "env-token"
        finally:
            del os.environ["TELEGRAM_BOT_TOKEN"]

    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            load_config("/nonexistent/config.yaml")

    def test_categories_loaded(self, config_file):
        config = load_config(config_file)
        assert len(config["categories"]) == 1
        assert config["categories"][0]["name"] == "Food"

    def test_server_defaults(self, tmp_path):
        minimal = {"gmail": {}, "server": {}, "web": {}, "telegram": {}}
        path = tmp_path / "config.yaml"
        with open(path, "w") as f:
            yaml.dump(minimal, f)
        config = load_config(str(path))
        assert config["server"]["port"] == 8080
        assert config["server"]["host"] == "0.0.0.0"
