"""Unit tests for config parsing and the X-Simulate-Failure parser."""

from app.config import load_settings, parse_database_url
from app.simulation import parse_simulation_header

KEYS = ["key_1", "key_2"]


def test_parse_database_url():
    assert parse_database_url("sqlite:////data/app.db") == "/data/app.db"
    assert parse_database_url("sqlite:///./app.db") == "./app.db"
    assert parse_database_url("/tmp/x.db") == "/tmp/x.db"
    assert parse_database_url(None) == "./app.db"


def test_key_ids_and_per_key_models():
    s = load_settings({"LLM_API_KEYS": "SECRET1, SECRET2 ,SECRET3", "LLM_MODEL": "m0", "LLM_KEY_MODELS": "m1"})
    assert s.key_ids == ["key_1", "key_2", "key_3"]
    assert s.api_keys == ("SECRET1", "SECRET2", "SECRET3")
    assert s.key_models == ("m1", "m0", "m0")
    assert "SECRET" not in repr(s)  # keys never printed


def test_origins_trailing_slash_removed():
    s = load_settings({"ALLOWED_ORIGINS": "https://x.vercel.app/, http://localhost:3000"})
    assert s.allowed_origins == ("https://x.vercel.app", "http://localhost:3000")


def test_simulation_parser():
    assert parse_simulation_header(None, KEYS) == {}
    assert parse_simulation_header("key_1=429", KEYS) == {"key_1": 429}
    assert parse_simulation_header("key_1=429,key_2=500", KEYS) == {"key_1": 429, "key_2": 500}
    assert parse_simulation_header("*=429", KEYS) == {"key_1": 429, "key_2": 429}
    assert parse_simulation_header("*=429,key_2=503", KEYS) == {"key_1": 429, "key_2": 503}
    assert parse_simulation_header(" key_1 = 502 ", KEYS) == {"key_1": 502}
    assert parse_simulation_header("key_1=404", KEYS) == {}
    assert parse_simulation_header("key_3=429", KEYS) == {}
    assert parse_simulation_header("nonsense,=,key_1=", KEYS) == {}
