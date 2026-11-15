"""Central configuration loaded from the local .env file.

Secrets are held in SecretStr fields so they never appear in reprs, logs or
error messages. Nothing in this module prints configuration values.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pydantic import BaseModel, Field, SecretStr

PROJECT_ROOT = Path(__file__).resolve().parent.parent
LOG_DIR = PROJECT_ROOT / "logs"
REPORT_DIR = PROJECT_ROOT / "reports"

PLACEHOLDER_KEYS = {"", "replace_with_new_rotated_key", "your_key_here", "sk-..."}


def _bool(value: str | None, default: bool = False) -> bool:
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int(value: str | None, default: int) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


class DatabaseSettings(BaseModel):
    host: str = "127.0.0.1"
    port: int = 3307
    name: str = "letura_intelligence"
    user: str = ""
    password: SecretStr = SecretStr("")


class AISettings(BaseModel):
    api_key: SecretStr = SecretStr("")
    model: str = "gpt-4.1-mini"
    enabled: bool = False
    max_output_tokens: int = Field(default=800, ge=64, le=4000)
    query_timeout_seconds: int = Field(default=15, ge=1, le=120)
    max_rows: int = Field(default=500, ge=1, le=5000)
    max_tool_rounds: int = Field(default=4, ge=1, le=8)
    readonly_user: str = "letura_ai_readonly"
    readonly_password: SecretStr = SecretStr("")

    @property
    def has_valid_key(self) -> bool:
        key = self.api_key.get_secret_value().strip()
        return key not in PLACEHOLDER_KEYS and key.startswith("sk-")

    @property
    def live_mode(self) -> bool:
        """True only if AI is enabled AND a plausible key is configured."""
        return self.enabled and self.has_valid_key


class Settings(BaseModel):
    db: DatabaseSettings
    ai: AISettings
    app_env: str = "local"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    load_dotenv(PROJECT_ROOT / ".env", override=False)
    env = os.environ
    return Settings(
        db=DatabaseSettings(
            host=env.get("DB_HOST", "127.0.0.1"),
            port=_int(env.get("DB_PORT"), 3307),
            name=env.get("DB_NAME", "letura_intelligence"),
            user=env.get("DB_USER", ""),
            password=SecretStr(env.get("DB_PASSWORD", "")),
        ),
        ai=AISettings(
            api_key=SecretStr(env.get("OPENAI_API_KEY", "")),
            model=env.get("OPENAI_MODEL", "gpt-4.1-mini").strip() or "gpt-4.1-mini",
            enabled=_bool(env.get("AI_ENABLED"), False),
            max_output_tokens=min(max(_int(env.get("AI_MAX_OUTPUT_TOKENS"), 800), 64), 4000),
            query_timeout_seconds=min(max(_int(env.get("AI_QUERY_TIMEOUT_SECONDS"), 15), 1), 120),
            readonly_user=env.get("AI_DB_USER", "letura_ai_readonly"),
            readonly_password=SecretStr(env.get("AI_DB_PASSWORD", "")),
        ),
        app_env=env.get("APP_ENV", "local"),
    )
