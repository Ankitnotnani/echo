"""LiteLLM gateway: ordered key pool, automatic failover and response caching.

How a request flows:
  1. Keys are tried in order (key_1, key_2, ...). Each attempt is one
     `litellm.acompletion` call with that key and `num_retries=0`, so failover
     is ours to control and deterministic.
  2. Before any key is tried, LiteLLM's built-in cache (in-memory or disk) is
     checked explicitly. The cache key is a SHA-256 of the model plus the full
     message list, exactly the rule in the assignment. A live reply is stored with
     its token usage, so a hit returns the identical text and the same tokens.
     (The lookup is explicit rather than via `acompletion(caching=True)` so the
     LLM_CACHE label never depends on LiteLLM-internal response fields.)
  3. A 429 / quota error / 5xx (or timeout, connection or auth error, or an empty
     reply) on one key moves on to the next key. If every key fails the caller
     gets AllProvidersUnavailable and answers 503.
  4. X-Simulate-Failure makes chosen keys raise the matching LiteLLM exception
     instead of calling the provider. It goes through the same `except` branch
     as a real failure, so the demo exercises the real failover path. Simulated
     requests skip the cache read (they still write), otherwise a cached prompt
     would hide the failover the header asks to demonstrate.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Optional

# Use LiteLLM's bundled model price map instead of fetching it at import time.
os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")

import litellm  # noqa: E402

from .config import Settings  # noqa: E402

logger = logging.getLogger("echo.gateway")

litellm.suppress_debug_info = True
litellm.drop_params = True  # drop params a provider does not support instead of erroring
try:
    litellm.telemetry = False
except Exception:  # pragma: no cover - attribute missing on some versions
    pass

CompletionFn = Callable[..., Awaitable[Any]]


class AllProvidersUnavailable(Exception):
    """Every key in the pool failed for this request."""

    def __init__(self, attempts: int) -> None:
        super().__init__(f"all {attempts} provider keys failed")
        self.attempts = attempts


class EmptyReplyError(Exception):
    status_code = 502


class SimulatedProviderError(Exception):
    """Fallback used only if a LiteLLM exception class cannot be constructed."""

    def __init__(self, status_code: int) -> None:
        super().__init__(f"simulated provider status {status_code}")
        self.status_code = status_code


@dataclass(frozen=True)
class KeySlot:
    key_id: str
    model: str
    api_key: str = field(repr=False)


@dataclass(frozen=True)
class GatewayResult:
    reply: str
    resolution_source: str  # "LIVE_INFERENCE" | "LLM_CACHE"
    model: str
    input_tokens: int
    output_tokens: int
    key_id: Optional[str]
    fallback_attempts: int


def _simulated_error(status: int, model: str) -> Exception:
    """Build the LiteLLM exception a real provider failure would raise."""
    message = f"Simulated HTTP {status} (X-Simulate-Failure)"
    provider = model.split("/", 1)[0] if "/" in model else "simulated"
    try:
        if status == 429:
            exc: Exception = litellm.RateLimitError(message=message, llm_provider=provider, model=model)
        elif status == 500:
            exc = litellm.InternalServerError(message=message, llm_provider=provider, model=model)
        elif status == 503:
            exc = litellm.ServiceUnavailableError(message=message, llm_provider=provider, model=model)
        else:  # 502
            exc = litellm.APIError(status_code=status, message=message, llm_provider=provider, model=model)
    except Exception:  # constructor signature differs on this LiteLLM version
        exc = SimulatedProviderError(status)
    try:
        setattr(exc, "simulated", True)
    except Exception:  # pragma: no cover
        pass
    return exc


def _status_of(exc: Exception) -> str:
    status = getattr(exc, "status_code", None)
    return str(status) if status is not None else "n/a"


def _extract_text(response: Any) -> str:
    try:
        content = response.choices[0].message.content
    except (AttributeError, IndexError, KeyError, TypeError):
        try:
            content = response["choices"][0]["message"]["content"]
        except Exception:
            content = None
    return (content or "").strip()


def _usage(response: Any, model: str, messages: list[dict[str, str]], reply: str) -> tuple[int, int]:
    usage = getattr(response, "usage", None)
    prompt = getattr(usage, "prompt_tokens", None) if usage is not None else None
    completion = getattr(usage, "completion_tokens", None) if usage is not None else None
    if prompt is None:
        try:
            prompt = litellm.token_counter(model=model, messages=messages)
        except Exception:
            prompt = 0
    if completion is None:
        try:
            completion = litellm.token_counter(model=model, text=reply)
        except Exception:
            completion = 0
    return int(prompt or 0), int(completion or 0)


class LLMGateway:
    def __init__(self, settings: Settings, completion_fn: Optional[CompletionFn] = None) -> None:
        self.settings = settings
        self.slots = [
            KeySlot(key_id=f"key_{i}", model=settings.key_models[i - 1], api_key=key)
            for i, key in enumerate(settings.api_keys, start=1)
        ]
        self._completion: CompletionFn = completion_fn or litellm.acompletion
        self.cache_enabled = False
        self.cache_type: Optional[str] = None
        self._store: Any = None  # LiteLLM cache backend (InMemoryCache / DiskCache)

    @property
    def key_ids(self) -> list[str]:
        return [slot.key_id for slot in self.slots]

    def setup_cache(self) -> None:
        """Enable LiteLLM's built-in cache: disk on the data volume, else in-memory."""
        cache_cls = getattr(litellm, "Cache", None)
        if cache_cls is None:  # pragma: no cover - very old/new layouts
            from litellm.caching.caching import Cache as cache_cls  # type: ignore

        ttl = self.settings.cache_ttl_seconds or None
        attempts: list[tuple[str, dict[str, Any]]] = []
        if self.settings.cache_type == "disk":
            os.makedirs(self.settings.cache_dir, exist_ok=True)
            attempts.append(("disk", {"type": "disk", "disk_cache_dir": self.settings.cache_dir}))
        attempts.append(("local", {"type": "local"}))

        for name, kwargs in attempts:
            for with_ttl in (True, False):
                try:
                    cache = cache_cls(**kwargs, ttl=ttl) if (with_ttl and ttl) else cache_cls(**kwargs)
                except Exception as exc:  # e.g. this LiteLLM version rejects `ttl` here
                    logger.warning(
                        "LiteLLM %s cache%s unavailable (%s: %s)",
                        name,
                        " with ttl" if with_ttl and ttl else "",
                        type(exc).__name__,
                        str(exc)[:160],
                    )
                    continue
                store = getattr(cache, "cache", None)  # the backend object behind litellm.Cache
                if store is None or not hasattr(store, "get_cache") or not hasattr(store, "set_cache"):
                    logger.warning("LiteLLM %s cache has no usable backend; trying next option", name)
                    break
                litellm.cache = cache
                self._store = store
                self.cache_enabled = True
                self.cache_type = name
                logger.info("LiteLLM cache enabled (%s)", name)
                return
        litellm.cache = None
        self._store = None
        self.cache_enabled = False
        logger.error("LiteLLM cache could not be enabled")

    @staticmethod
    def cache_key(model: str, messages: list[dict[str, str]]) -> str:
        """model + the full message list (system prompt + history + new message)."""
        payload = json.dumps({"model": model, "messages": messages}, sort_keys=True, ensure_ascii=False)
        return "echo:chat:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _cache_get(self, key: str) -> Optional[dict[str, Any]]:
        if not self._store:
            return None
        try:
            value = self._store.get_cache(key)
            if isinstance(value, (str, bytes)):
                value = json.loads(value)
            if isinstance(value, dict) and value.get("reply"):
                return value
        except Exception as exc:  # a cache problem must never break chat
            logger.warning("cache read failed: %s", type(exc).__name__)
        return None

    def _cache_set(self, key: str, entry: dict[str, Any]) -> None:
        if not self._store:
            return
        try:
            ttl = self.settings.cache_ttl_seconds or None
            self._store.set_cache(key, json.dumps(entry), ttl=ttl)
        except Exception as exc:
            logger.warning("cache write failed: %s", type(exc).__name__)

    async def complete(self, messages: list[dict[str, str]], simulated: dict[str, int]) -> GatewayResult:
        if not self.slots:
            raise AllProvidersUnavailable(0)

        # Cache lookup (skipped for simulated requests, so the requested failover is really exercised).
        primary_model = self.slots[0].model
        key = self.cache_key(primary_model, messages)
        if not simulated:
            hit = self._cache_get(key)
            if hit is not None:
                return GatewayResult(
                    reply=str(hit["reply"]),
                    resolution_source="LLM_CACHE",
                    model=str(hit.get("model") or primary_model),
                    input_tokens=int(hit.get("input_tokens") or 0),
                    output_tokens=int(hit.get("output_tokens") or 0),
                    key_id=None,
                    fallback_attempts=0,
                )

        failures = 0
        for slot in self.slots:
            try:
                if slot.key_id in simulated:
                    raise _simulated_error(simulated[slot.key_id], slot.model)

                kwargs: dict[str, Any] = {
                    "model": slot.model,
                    "messages": messages,
                    "api_key": slot.api_key,
                    "timeout": self.settings.llm_timeout_seconds,
                    "max_tokens": self.settings.llm_max_tokens,
                    "temperature": self.settings.llm_temperature,
                    "num_retries": 0,
                    "caching": False,  # caching is handled explicitly above/below
                }
                if self.settings.llm_reasoning_effort:
                    kwargs["reasoning_effort"] = self.settings.llm_reasoning_effort

                response = await self._completion(**kwargs)
                reply = _extract_text(response)
                if not reply:
                    raise EmptyReplyError("provider returned an empty reply")
            except Exception as exc:  # any provider failure -> next key
                failures += 1
                # Log only the type and status: provider messages can echo URLs with keys.
                logger.warning(
                    "%s failed: %s status=%s%s",
                    slot.key_id,
                    type(exc).__name__,
                    _status_of(exc),
                    " (simulated)" if getattr(exc, "simulated", False) else "",
                )
                continue

            input_tokens, output_tokens = _usage(response, slot.model, messages, reply)
            # Store under the request's cache key (model of the pool's first slot + messages).
            self._cache_set(
                key,
                {"reply": reply, "model": slot.model, "input_tokens": input_tokens, "output_tokens": output_tokens},
            )
            return GatewayResult(
                reply=reply,
                resolution_source="LIVE_INFERENCE",
                model=slot.model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                key_id=slot.key_id,
                fallback_attempts=failures,
            )

        raise AllProvidersUnavailable(failures)
