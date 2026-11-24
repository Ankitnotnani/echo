"""Contract tests for /health, /chat and /sessions/{id}/messages."""

from __future__ import annotations

import litellm

from conftest import KEY_ONE, MODEL, FakeProvider, chat

META_FIELDS = {
    "resolution_source",
    "model",
    "latency_ms",
    "input_tokens",
    "output_tokens",
    "key_id",
    "fallback_attempts",
}


def rate_limit():
    return litellm.RateLimitError(message="quota exceeded", llm_provider="gemini", model=MODEL)


# ---------------------------------------------------------------- health


def test_health_ok(client):
    client_, _ = client
    r = client_.get("/health")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["keys_configured"] == 2
    assert body["cache_enabled"] is True


def test_health_without_keys_is_503_json(make_client):
    c, _ = make_client(keys="")
    r = c.get("/health")
    assert r.status_code == 503
    assert "detail" in r.json()


# ---------------------------------------------------------------- happy path


def test_chat_happy_path_contract(client):
    c, _ = client
    r = chat(c, "s-happy", "What is the capital of France?")
    assert r.status_code == 200
    body = r.json()
    assert set(body) >= {"session_id", "reply", "metadata"}
    assert body["session_id"] == "s-happy"
    assert body["reply"]
    meta = body["metadata"]
    assert set(meta) >= META_FIELDS
    assert meta["resolution_source"] == "LIVE_INFERENCE"
    assert meta["model"] == MODEL
    assert meta["key_id"] == "key_1"
    assert meta["fallback_attempts"] == 0
    for field in ("latency_ms", "input_tokens", "output_tokens"):
        assert isinstance(meta[field], int) and meta[field] >= 0
    assert meta["input_tokens"] > 0 and meta["output_tokens"] > 0


# ---------------------------------------------------------------- validation


def test_validation_errors_are_422_and_not_stored(client):
    c, provider = client
    bad_bodies = [
        {"session_id": "s-v"},  # missing message
        {"message": "hi"},  # missing session_id
        {"session_id": "s-v", "message": "    "},  # whitespace only
        {"session_id": "s-v", "message": ""},
        {"session_id": "s-v", "message": "x" * 4001},  # too long
        {"session_id": "", "message": "hi"},
        {"session_id": "   ", "message": "hi"},
        {"session_id": "s" * 129, "message": "hi"},
        {"session_id": "s-v", "message": 123},  # wrong type
        {"session_id": "s-v", "message": None},
    ]
    for body in bad_bodies:
        r = c.post("/chat", json=body)
        assert r.status_code == 422, body
        assert "detail" in r.json()

    r = c.post("/chat", content=b"{not json", headers={"Content-Type": "application/json"})
    assert r.status_code == 422
    assert "detail" in r.json()

    assert provider.all_calls == []
    assert c.get("/sessions/s-v/messages").status_code == 404


def test_message_is_trimmed_and_4000_chars_is_allowed(client):
    c, _ = client
    r = chat(c, "s-trim", "  " + "y" * 4000 + "  ")
    assert r.status_code == 200
    stored = c.get("/sessions/s-trim/messages").json()["messages"][0]["content"]
    assert stored == "y" * 4000


# ---------------------------------------------------------------- caching


def test_same_first_message_in_new_session_is_cache_hit(client):
    c, provider = client
    first = chat(c, "s-cache-a", "What is the capital of France?").json()
    second = chat(c, "s-cache-b", "What is the capital of France?").json()

    assert first["metadata"]["resolution_source"] == "LIVE_INFERENCE"
    assert second["metadata"]["resolution_source"] == "LLM_CACHE"
    assert second["reply"] == first["reply"]
    assert second["metadata"]["key_id"] is None
    assert second["metadata"]["fallback_attempts"] == 0
    assert second["metadata"]["input_tokens"] == first["metadata"]["input_tokens"]
    assert second["metadata"]["output_tokens"] == first["metadata"]["output_tokens"]
    assert second["metadata"]["latency_ms"] < first["metadata"]["latency_ms"]
    assert len(provider.live_calls) == 1


def test_different_message_is_never_from_cache(client):
    c, _ = client
    chat(c, "s-d1", "What is the capital of France?")
    r = chat(c, "s-d2", "What is the capital of Spain?").json()
    assert r["metadata"]["resolution_source"] == "LIVE_INFERENCE"


def test_cache_is_shared_across_keys(client):
    """The cache key must not include the API key: a reply produced by key_2
    is served from cache later even though key_1 is tried first."""
    c, provider = client
    provider.fail[KEY_ONE] = rate_limit
    live = chat(c, "s-x1", "Shared cache?").json()
    assert live["metadata"]["key_id"] == "key_2"
    provider.fail.clear()
    hit = chat(c, "s-x2", "Shared cache?").json()
    assert hit["metadata"]["resolution_source"] == "LLM_CACHE"


def test_different_system_prompt_changes_cache_key(client):
    c, _ = client
    chat(c, "s-p1", "Hello there")
    r = chat(c, "s-p2", "Hello there", system_prompt="Answer like a pirate.").json()
    assert r["metadata"]["resolution_source"] == "LIVE_INFERENCE"


def test_disk_cache_works(make_client):
    c, _ = make_client(cache_type="disk")
    assert c.get("/health").json()["cache_enabled"] is True
    chat(c, "s-disk-1", "Disk cache please")
    r = chat(c, "s-disk-2", "Disk cache please").json()
    assert r["metadata"]["resolution_source"] == "LLM_CACHE"


# ---------------------------------------------------------------- failover


def test_simulated_single_key_failures_fail_over_to_key_2(client):
    c, _ = client
    for i, status in enumerate((429, 500, 502, 503)):
        r = chat(c, f"s-sim-{i}", f"Failover question {i}", {"X-Simulate-Failure": f"key_1={status}"})
        assert r.status_code == 200, status
        meta = r.json()["metadata"]
        assert meta["key_id"] == "key_2"
        assert meta["fallback_attempts"] == 1
        assert meta["resolution_source"] == "LIVE_INFERENCE"
        assert r.json()["reply"].startswith("Answer to:")  # a real answer, not an error in a 200


def test_all_keys_failing_returns_503_and_saves_nothing(client):
    c, _ = client
    for header in ("*=429", "key_1=429,key_2=500", " key_1 = 503 , key_2=502 "):
        r = chat(c, "s-down", "Will this fail?", {"X-Simulate-Failure": header})
        assert r.status_code == 503, header
        assert r.json() == {"detail": "all providers unavailable"}
    assert c.get("/sessions/s-down/messages").status_code == 404


def test_503_does_not_touch_existing_history(client):
    c, _ = client
    chat(c, "s-keep", "First message")
    r = chat(c, "s-keep", "Second message", {"X-Simulate-Failure": "*=429"})
    assert r.status_code == 503
    assert len(c.get("/sessions/s-keep/messages").json()["messages"]) == 2


def test_explicit_pair_overrides_wildcard(client):
    c, _ = client
    # key_2 gets 500 from its explicit pair, key_1 gets 429 from "*": both fail.
    r = chat(c, "s-ovr", "override", {"X-Simulate-Failure": "*=429,key_2=500"})
    assert r.status_code == 503


def test_simulation_ignored_when_flag_off(make_client):
    c, _ = make_client(simulation=False)
    r = chat(c, "s-off", "No simulation", {"X-Simulate-Failure": "*=429"})
    assert r.status_code == 200
    assert r.json()["metadata"]["key_id"] == "key_1"


def test_invalid_simulation_values_are_ignored(client):
    c, _ = client
    r = chat(c, "s-inv", "Invalid header", {"X-Simulate-Failure": "key_1=418,key_9=429,garbage"})
    assert r.status_code == 200
    assert r.json()["metadata"]["key_id"] == "key_1"


def test_simulation_skips_cache_read(client):
    c, _ = client
    chat(c, "s-c1", "Cached then simulated")
    r = chat(c, "s-c2", "Cached then simulated", {"X-Simulate-Failure": "key_1=429"}).json()
    assert r["metadata"]["resolution_source"] == "LIVE_INFERENCE"
    assert r["metadata"]["key_id"] == "key_2"
    r = chat(c, "s-c3", "Cached then simulated", {"X-Simulate-Failure": "*=429"})
    assert r.status_code == 503


def test_real_provider_rate_limit_fails_over(client):
    c, provider = client
    provider.fail[KEY_ONE] = rate_limit
    r = chat(c, "s-real", "Real 429 from key_1")
    assert r.status_code == 200
    assert r.json()["metadata"]["key_id"] == "key_2"
    assert r.json()["metadata"]["fallback_attempts"] == 1


def test_failures_are_per_request_only(client):
    c, _ = client
    chat(c, "s-once-1", "one", {"X-Simulate-Failure": "key_1=429"})
    r = chat(c, "s-once-2", "two").json()
    assert r["metadata"]["key_id"] == "key_1"  # no cooldown left behind


# ---------------------------------------------------------------- multi-turn + history


def test_multi_turn_sends_history_and_sessions_stay_separate(client):
    c, provider = client
    chat(c, "s-mt", "My income is 50000")
    chat(c, "s-other", "Unrelated")
    chat(c, "s-mt", "What is my income?")

    sent = provider.live_calls[-1]["messages"]
    assert [m["role"] for m in sent] == ["system", "user", "assistant", "user"]
    assert sent[1]["content"] == "My income is 50000"
    assert all("Unrelated" not in m["content"] for m in sent)


def test_history_endpoint_shape(client):
    c, _ = client
    chat(c, "s-h", "Hi")
    chat(c, "s-h", "Again")
    r = c.get("/sessions/s-h/messages")
    assert r.status_code == 200
    body = r.json()
    assert body["session_id"] == "s-h"
    msgs = body["messages"]
    assert [m["role"] for m in msgs] == ["user", "assistant", "user", "assistant"]
    assert [m["content"] for m in msgs[::2]] == ["Hi", "Again"]
    assert "metadata" not in msgs[0]
    assert msgs[1]["metadata"]["resolution_source"] in {"LIVE_INFERENCE", "LLM_CACHE"}
    assert {"input_tokens", "output_tokens"} <= set(msgs[1]["metadata"])
    assert all(m["role"] != "system" for m in msgs)


def test_unknown_session_is_404(client):
    c, _ = client
    r = c.get("/sessions/does-not-exist/messages")
    assert r.status_code == 404
    assert r.json() == {"detail": "session not found"}


def test_system_prompt_override_persists_for_session(client):
    c, provider = client
    chat(c, "s-sp", "Hello", system_prompt="You are terse.")
    chat(c, "s-sp", "And again")
    assert provider.live_calls[-1]["messages"][0] == {"role": "system", "content": "You are terse."}


def test_tokens_are_per_request_not_cumulative(client):
    c, _ = client
    a = chat(c, "s-t1", "Tell me about budgets").json()["metadata"]
    b = chat(c, "s-t2", "Tell me about savings").json()["metadata"]  # same length
    assert abs(a["input_tokens"] - b["input_tokens"]) <= 2
    second_turn = chat(c, "s-t1", "And more").json()["metadata"]
    # Each stored assistant message keeps its own request's usage, not a running total.
    stored = [m["metadata"] for m in c.get("/sessions/s-t1/messages").json()["messages"] if m["role"] == "assistant"]
    assert stored[0]["output_tokens"] == a["output_tokens"]
    assert stored[1]["output_tokens"] == second_turn["output_tokens"]
    assert second_turn["input_tokens"] >= a["input_tokens"]  # the prompt now carries history


# ---------------------------------------------------------------- robustness


def test_provider_crash_on_every_key_is_clean_503(make_client):
    class Boom(FakeProvider):
        async def __call__(self, **kwargs):
            raise RuntimeError("provider exploded")

    c, _ = make_client(provider=Boom())
    # Any provider-side crash counts as that key failing -> 503, never a trace.
    r = chat(c, "s-boom", "crash")
    assert r.status_code == 503
    assert "Traceback" not in r.text


def test_handler_crash_returns_json_500(client):
    c, _ = client
    c.app.state.db.list_messages = lambda session_id: 1 / 0  # force a bug
    r = c.get("/sessions/anything/messages")
    assert r.status_code == 500
    assert r.json() == {"detail": "internal server error"}
    assert "Traceback" not in r.text


def test_unknown_route_is_json(client):
    c, _ = client
    r = c.get("/nope")
    assert r.status_code == 404
    assert "detail" in r.json()


def test_history_persists_across_restart(make_client):
    c1, _ = make_client(db_name="persist.db")
    chat(c1, "s-persist", "Remember me")
    c2, _ = make_client(db_name="persist.db")
    r = c2.get("/sessions/s-persist/messages")
    assert r.status_code == 200
    assert r.json()["messages"][0]["content"] == "Remember me"


def test_cors_preflight_allows_simulation_header(client):
    c, _ = client
    r = c.options(
        "/chat",
        headers={
            "Origin": "https://echo-chat.vercel.app",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type,x-simulate-failure",
        },
    )
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == "https://echo-chat.vercel.app"

    r = c.options(
        "/chat",
        headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"},
    )
    assert r.headers.get("access-control-allow-origin") is None


def test_docs_disabled_by_default(client):
    c, _ = client
    assert c.get("/docs").status_code == 404
    assert c.get("/openapi.json").status_code == 404
