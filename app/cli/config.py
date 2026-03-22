"""
CLI configuration — resolves base URL and API token from env vars or config file.
"""
import os
import tomllib
from pathlib import Path

_CONFIG_PATH = Path.home() / ".config" / "gatekeeper" / "config.toml"

_DEFAULT_URL = "http://localhost:8000"


def _load_file() -> dict:
    if _CONFIG_PATH.exists():
        with open(_CONFIG_PATH, "rb") as f:
            return tomllib.load(f)
    return {}


def resolve_url(override: str | None = None) -> str:
    if override:
        return override.rstrip("/")
    if env := os.environ.get("GK_API_URL"):
        return env.rstrip("/")
    cfg = _load_file()
    return cfg.get("url", _DEFAULT_URL).rstrip("/")


def resolve_token(override: str | None = None) -> str | None:
    if override:
        return override
    if env := os.environ.get("GK_API_TOKEN"):
        return env
    cfg = _load_file()
    return cfg.get("token")


def save_config(url: str, token: str) -> None:
    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    content = f'url = "{url}"\ntoken = "{token}"\n'
    _CONFIG_PATH.write_text(content)
