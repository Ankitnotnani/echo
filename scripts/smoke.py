"""Contract smoke test for a running Echo backend (local or deployed).

Usage:
    python scripts/smoke.py http://localhost:8000
    python scripts/smoke.py https://echo-api.onrender.com

Uses only the Python standard library, so it runs on Windows, macOS and Linux.
It makes about 8 real LLM calls (the rest are cache hits or simulated failures).
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request
import uuid

BASE = (sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000").rstrip("/")
results: list[tuple[bool, str]] = []


def call(method: str, path: str, body=None, headers=None, raw: bytes | None = None, timeout=120):
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    req = urllib.request.Request(BASE + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    for k, v in (headers or {}).items():
        req.add_header(k, v)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            return res.status, json.loads(res.read() or b"null")
    except urllib.error.HTTPError as err:
        text = err.read()
        try:
            return err.code, json.loads(text)
        except json.JSONDecodeError:
            return err.code, {"_raw": text.decode(errors="replace")[:200]}


def check(ok: bool, label: str) -> bool:
    ok = bool(ok)
    results.append((ok, label))
    print(("  PASS  " if ok else "  FAIL  ") + label)
    return ok


def sid() -> str:
    return f"smoke-{uuid.uuid4().hex[:12]}"


print(f"Echo smoke test against {BASE}\n")

# 1. health (first call may wake a sleeping free-tier server)
status, body = call("GET", "/health", timeout=120)
check(status == 200 and body.get("status") == "ok", f"GET /health -> 200 ok  ({body})")
check(isinstance(body, dict) and body.get("keys_configured", 0) >= 2, "keys_configured >= 2")
check(isinstance(body, dict) and body.get("cache_enabled") is True, "cache_enabled is true")

# 2. live call with a unique message
nonce = uuid.uuid4().hex[:8]
question = f"In one short sentence, what is the capital of Japan? (ref {nonce})"
s1 = sid()
status, live = call("POST", "/chat", {"session_id": s1, "message": question})
meta = live.get("metadata", {}) if isinstance(live, dict) else {}
check(status == 200 and live.get("reply"), f"POST /chat -> 200 with a reply  (status {status})")
check(meta.get("resolution_source") == "LIVE_INFERENCE", f"first call is LIVE_INFERENCE  ({meta.get('resolution_source')})")
check(meta.get("key_id") == "key_1" and meta.get("fallback_attempts") == 0, f"key_1 answered, 0 fallbacks  ({meta.get('key_id')}, {meta.get('fallback_attempts')})")
fields = {"resolution_source", "model", "latency_ms", "input_tokens", "output_tokens", "key_id", "fallback_attempts"}
check(fields <= set(meta), f"metadata has every contract field  (missing: {sorted(fields - set(meta))})")
check(all(isinstance(meta.get(f), int) for f in ("latency_ms", "input_tokens", "output_tokens", "fallback_attempts")), "latency and tokens are integers")

# 3. same first message in a NEW session -> cache hit
status, hit = call("POST", "/chat", {"session_id": sid(), "message": question})
hmeta = hit.get("metadata", {}) if isinstance(hit, dict) else {}
check(hmeta.get("resolution_source") == "LLM_CACHE", f"same message, new session -> LLM_CACHE  ({hmeta.get('resolution_source')})")
check(hit.get("reply") == live.get("reply"), "cache hit returns the identical reply")
check(hmeta.get("key_id") is None and hmeta.get("fallback_attempts") == 0, "cache hit: key_id null, 0 fallbacks")
check(hmeta.get("latency_ms", 1e9) < meta.get("latency_ms", 0), f"cache hit faster than live  ({hmeta.get('latency_ms')} ms < {meta.get('latency_ms')} ms)")

# 4. failover
for status_code in (429, 500):
    status, fo = call("POST", "/chat", {"session_id": sid(), "message": f"Say OK. (failover {status_code} {nonce})"}, {"X-Simulate-Failure": f"key_1={status_code}"})
    fmeta = fo.get("metadata", {}) if isinstance(fo, dict) else {}
    check(status == 200 and fmeta.get("key_id") == "key_2" and fmeta.get("fallback_attempts") == 1,
          f"X-Simulate-Failure key_1={status_code} -> 200 from key_2, 1 fallback  ({status}, {fmeta.get('key_id')}, {fmeta.get('fallback_attempts')})")

s_down = sid()
status, down = call("POST", "/chat", {"session_id": s_down, "message": "This should fail"}, {"X-Simulate-Failure": "*=429"})
check(status == 503 and down == {"detail": "all providers unavailable"}, f"X-Simulate-Failure *=429 -> 503 all providers unavailable  ({status}, {down})")
status, _ = call("GET", f"/sessions/{s_down}/messages")
check(status == 404, "failed request was not saved (history 404)")

# 5. validation
status, body = call("POST", "/chat", {"session_id": sid(), "message": "x" * 4001})
check(status == 422 and "detail" in body, "message over 4000 chars -> 422")
status, body = call("POST", "/chat", {"session_id": sid(), "message": "   "})
check(status == 422 and "detail" in body, "whitespace-only message -> 422")
status, body = call("POST", "/chat", {"message": "hi"})
check(status == 422 and "detail" in body, "missing session_id -> 422")
status, body = call("POST", "/chat", raw=b"{not json")
check(status == 422 and "detail" in body, "malformed JSON -> 422")

# 6. multi-turn + history
s_mt = sid()
call("POST", "/chat", {"session_id": s_mt, "message": f"Remember this: my favourite colour is teal. Reply OK. ({nonce})"})
status, recall = call("POST", "/chat", {"session_id": s_mt, "message": "What is my favourite colour? One word."})
check(status == 200 and "teal" in recall.get("reply", "").lower(), f"bot remembers earlier message  ({recall.get('reply', '')[:60]!r})")
status, hist = call("GET", f"/sessions/{s_mt}/messages")
msgs = hist.get("messages", []) if isinstance(hist, dict) else []
check(status == 200 and [m.get("role") for m in msgs] == ["user", "assistant", "user", "assistant"], "history oldest-first: user, assistant, user, assistant")
check(all("metadata" in m for m in msgs if m.get("role") == "assistant") and all("metadata" not in m for m in msgs if m.get("role") == "user"), "metadata on assistant messages only")
status, body = call("GET", f"/sessions/does-not-exist-{nonce}/messages")
check(status == 404 and body == {"detail": "session not found"}, "unknown session -> 404 session not found")

passed = sum(ok for ok, _ in results)
print(f"\n{passed}/{len(results)} checks passed")
sys.exit(0 if passed == len(results) else 1)
