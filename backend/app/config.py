"""Settings, read once from environment variables.

Every value has a safe default so the app can start (and report an unhealthy
/health) even when misconfigured, instead of crashing on import.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Mapping, Optional

from .prompts import DEFAULT_SYSTEM_PROMPT

DEFAULT_MODEL = "gemini/gemini-3.5-flash-lite"


def _csv(value: Optional[str]) -> list[str]:
    if not value:
        return []
    return [item.strip() for item in value.split(",") if item.strip()]


def _bool(value: Optional[str], default: bool = False) -> bool:
    if value is None or value.strip() == "":
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int(value: Optional[str], default: int) -> int:
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default


def _float(value: Optional[str], default: float) -> float:
    try:
        return float(str(value).strip())
    except (TypeError, ValueError):
        return default


def parse_database_url(url: Optional[str]) -> str:
    """Turn a SQLAlchemy-style SQLite URL into a filesystem path.

    sqlite:////data/app.db  -> /data/app.db   (absolute, 4 slashes)
    sqlite:///./app.db      -> ./app.db       (relative, 3 slashes)
    /data/app.db            -> /data/app.db   (a bare path is accepted too)
    """
    if not url:
        return "./app.db"
    url = url.strip()
    prefix = "sqlite:///"
    if url.startswith(prefix):
        return url[len(prefix):] or "./app.db"
    if url.startswith("sqlite://"):
        raise ValueError("DATABASE_URL must look like sqlite:////data/app.db")
    return url


@dataclass(frozen=True)
class Settings:
    api_keys: tuple[str, ...]
    key_models: tuple[str, ...]
    model: str
    database_path: str
    allowed_origins: tuple[str, ...]
    allowed_origin_regex: Optional[str]
    enable_failure_simulation: bool
    default_system_prompt: str
    cache_type: str
    cache_dir: str
    cache_ttl_seconds: int
    llm_timeout_seconds: float
    llm_max_tokens: int
    llm_temperature: float
    llm_reasoning_effort: Optional[str]
    max_history_messages: int
    enable_docs: bool
    log_level: str

    def __repr__(self) -> str:  # never print keys
        return f"Settings(keys={len(self.api_keys)}, model={self.model!r}, db={self.database_path!r})"

    @property
    def key_ids(self) -> list[str]:
        return [f"key_{i}" for i in range(1, len(self.api_keys) + 1)]


def load_settings(env: Optional[Mapping[str, str]] = None) -> Settings:
    env = os.environ if env is None else env

    api_keys = tuple(_csv(env.get("LLM_API_KEYS")))
    model = (env.get("LLM_MODEL") or DEFAULT_MODEL).strip()

    # Optional per-key models (e.g. key_1 on Gemini, key_2 on Groq). Missing
    # entries fall back to LLM_MODEL; extra entries are ignored.
    per_key = _csv(env.get("LLM_KEY_MODELS"))
    key_models = tuple(per_key[i] if i < len(per_key) else model for i in range(len(api_keys)))

    origins = tuple(o.rstrip("/") for o in _csv(env.get("ALLOWED_ORIGINS", "http://localhost:3000")))
    effort = (env.get("LLM_REASONING_EFFORT") or "").strip() or None

    return Settings(
        api_keys=api_keys,
        key_models=key_models,
        model=model,
        database_path=parse_database_url(env.get("DATABASE_URL")),
        allowed_origins=origins,
        allowed_origin_regex=(env.get("ALLOWED_ORIGIN_REGEX") or "").strip() or None,
        enable_failure_simulation=_bool(env.get("ENABLE_FAILURE_SIMULATION"), False),
        default_system_prompt=(env.get("DEFAULT_SYSTEM_PROMPT") or "").strip() or DEFAULT_SYSTEM_PROMPT,
        cache_type=(env.get("CACHE_TYPE") or "disk").strip().lower(),
        cache_dir=(env.get("CACHE_DIR") or "./llm_cache").strip(),
        cache_ttl_seconds=_int(env.get("CACHE_TTL_SECONDS"), 86400),
        llm_timeout_seconds=_float(env.get("LLM_TIMEOUT_SECONDS"), 30.0),
        llm_max_tokens=_int(env.get("LLM_MAX_TOKENS"), 2048),
        llm_temperature=_float(env.get("LLM_TEMPERATURE"), 0.3),
        llm_reasoning_effort=effort,
        max_history_messages=max(0, _int(env.get("MAX_HISTORY_MESSAGES"), 40)),
        enable_docs=_bool(env.get("ENABLE_DOCS"), False),
        log_level=(env.get("LOG_LEVEL") or "info").strip().upper(),
    )
