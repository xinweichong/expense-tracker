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

    def test_missing_file_falls_back_to_env(self, monkeypatch):
        """When config.yaml is absent, load_config falls back to env vars."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "fallback-token")
        config = load_config("/nonexistent/config.yaml")
        assert config["telegram"]["bot_token"] == "fallback-token"
        assert config["server"]["port"] == 8080

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


class TestEnvConfig:
    def test_config_from_env(self, monkeypatch, tmp_path):
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "env-token")
        monkeypatch.setenv("WEB_PASSWORD_HASH", "$2b$12$envhash")
        monkeypatch.setenv("SERVER_PORT", "9090")
        config = load_config(str(tmp_path / "nonexistent.yaml"))
        assert config["telegram"]["bot_token"] == "env-token"
        assert config["web"]["password_hash"] == "$2b$12$envhash"

    def test_config_from_env_server_port(self, monkeypatch, tmp_path):
        monkeypatch.setenv("SERVER_PORT", "9090")
        config = load_config(str(tmp_path / "nonexistent.yaml"))
        assert config["server"]["port"] == 9090

    def test_config_from_env_port_override(self, monkeypatch, tmp_path):
        """PORT env var should take precedence over SERVER_PORT."""
        monkeypatch.setenv("SERVER_PORT", "9090")
        monkeypatch.setenv("PORT", "8081")
        config = load_config(str(tmp_path / "nonexistent.yaml"))
        assert config["server"]["port"] == 8081

    def test_config_from_env_default_categories(self, monkeypatch, tmp_path):
        """Env-var config should include default categories."""
        monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "env-token")
        config = load_config(str(tmp_path / "nonexistent.yaml"))
        assert len(config["categories"]) > 0
        cat_names = [c["name"] for c in config["categories"]]
        assert "Food" in cat_names
        assert "Transport" in cat_names

    def test_config_from_env_gmail_settings(self, monkeypatch, tmp_path):
        monkeypatch.setenv("GMAIL_SENDER_FILTERS", "a@b.com,c@d.com")
        monkeypatch.setenv("GMAIL_POLL_INTERVAL", "60")
        config = load_config(str(tmp_path / "nonexistent.yaml"))
        assert config["gmail"]["sender_filters"] == ["a@b.com", "c@d.com"]
        assert config["gmail"]["poll_interval_seconds"] == 60

    def test_config_from_env_webhook_url(self, monkeypatch, tmp_path):
        monkeypatch.setenv("WEBHOOK_BASE_URL", "https://example.com")
        config = load_config(str(tmp_path / "nonexistent.yaml"))
        assert config["server"]["webhook_base_url"] == "https://example.com"
