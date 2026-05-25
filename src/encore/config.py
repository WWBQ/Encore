"""Configuration loading for Encore adapters."""

import os
import yaml
from pathlib import Path

CONFIG_DIR = Path(os.environ.get("ENCORE_CONFIG_DIR", Path.home() / ".encore"))
CONFIG_PATH = CONFIG_DIR / "config.yaml"

DEFAULT_CONFIG = {
    "adapters": {
        "local": {"enabled": True},
        "github": {"enabled": False},
        "feishu": {"enabled": False},
        "notion": {"enabled": False},
    }
}
def load_config() -> dict:
    """Load config from ~/.encore/config.yaml, creating default if absent."""
    if not CONFIG_PATH.exists():
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            yaml.dump(DEFAULT_CONFIG, f, allow_unicode=True, default_flow_style=False)
        return DEFAULT_CONFIG

    with open(CONFIG_PATH, encoding="utf-8") as f:
        config = yaml.safe_load(f)
    if not config or "adapters" not in config:
        return DEFAULT_CONFIG
    return config
def save_config(config: dict) -> None:
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, default_flow_style=False)
    CONFIG_PATH.chmod(0o600)
def get_enabled_adapters(config: dict | None = None) -> dict[str, dict]:
    """Return {adapter_name: adapter_config} for all enabled adapters."""
    if config is None:
        config = load_config()
    adapters = config.get("adapters", {})
    return {name: cfg for name, cfg in adapters.items() if cfg.get("enabled")}
