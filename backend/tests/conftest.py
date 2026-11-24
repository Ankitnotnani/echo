"""Test fixtures.

The provider is faked at the `litellm.acompletion` boundary: every call still
goes through the real LiteLLM function, but with `mock_response`, so no network
or quota is used. The gateway's real LiteLLM cache backend is used as-is.
Keys can be told to fail with a real LiteLLM exception, as a provider would.
"""

from __future__ import annotations

import asyncio
from typing import Callable, Optional

import litellm
import pytest
from fastapi.testclient import TestClient

from app.config import load_settings
from app.gateway import LLMGateway
from app.main import create_app

KEY_ONE = "test-key-one"
KEY_TWO = "test-key-two"
MODEL = "gemini/gemini-2.5-flash"


class FakeProvider:
    def __init__(self, live_delay: float = 0.05) -> None:
        self.live_delay = live_delay
        self.fail: dict[str, Callable[[], Exception]] = {}
        self.live_calls: list[dict] = []  # calls that reached the (mock) provider
        self.all_calls: list[dict] = []

    def reply_for(self, messages: list[dict]) -> str:
        last = messages[-1]["content"]
        turns = sum(1 for m in messages if m["role"] == "user")
        return f"Answer to: {last} (turn {turns})"

    async def __call__(self, **kwargs):
        self.all_calls.append(kwargs)
        api_key = kwargs.get("api_key")
        if api_key in self.fail:
            raise self.fail[api_key]()
        response = await litellm.acompletion(**kwargs, mock_response=self.reply_for(kwargs["messages"]))
        self.live_calls.append(kwargs)
        await asyncio.sleep(self.live_delay)  # a live call is slower than a cache hit
        return response


@pytest.fixture
def make_client(tmp_path):
    clients: list[TestClient] = []

    def _make(
        *,
        simulation: bool = True,
        keys: str = f"{KEY_ONE},{KEY_TWO}",
        db_name: str = "app.db",
        cache_type: str = "local",
        provider: Optional[FakeProvider] = None,
        extra_env: Optional[dict] = None,
    ):
        env = {
            "LLM_API_KEYS": keys,
            "LLM_MODEL": MODEL,
            "DATABASE_URL": f"sqlite:///{tmp_path / db_name}",
            "ALLOWED_ORIGINS": "http://localhost:3000,https://echo-chat.vercel.app",
            "ENABLE_FAILURE_SIMULATION": "true" if simulation else "false",
            "CACHE_TYPE": cache_type,
            "CACHE_DIR": str(tmp_path / "llm_cache"),
            "LOG_LEVEL": "warning",
        }
        env.update(extra_env or {})
        settings = load_settings(env)
        provider = provider or FakeProvider()
        gateway = LLMGateway(settings, completion_fn=provider)
        app = create_app(settings, gateway=gateway)
        client = TestClient(app, raise_server_exceptions=False)
        client.__enter__()  # run the lifespan: schema + cache setup
        clients.append(client)
        return client, provider

    yield _make

    for client in clients:
        client.__exit__(None, None, None)
    litellm.cache = None


@pytest.fixture
def client(make_client):
    return make_client()


def chat(client, session_id: str, message: str, headers: Optional[dict] = None, **extra):
    body = {"session_id": session_id, "message": message, **extra}
    return client.post("/chat", json=body, headers=headers or {})
