"""X-Simulate-Failure header parsing.

Format: comma-separated `<key_id>=<status>` pairs, `*` meaning every key.
    key_1=429
    key_1=429,key_2=500
    *=429
Only 429, 500, 502 and 503 are honoured. Invalid pairs and unknown key ids are
ignored. An explicit pair overrides `*` for its key. The result applies to one
request only; nothing is remembered between requests.
"""

from __future__ import annotations

import logging
from typing import Iterable, Optional

ALLOWED_STATUSES = frozenset({429, 500, 502, 503})

logger = logging.getLogger("echo.simulation")


def parse_simulation_header(value: Optional[str], key_ids: Iterable[str]) -> dict[str, int]:
    key_ids = list(key_ids)
    if not value or not value.strip():
        return {}

    wildcard: Optional[int] = None
    explicit: dict[str, int] = {}

    for raw in value.split(","):
        part = raw.strip()
        if not part:
            continue
        key, sep, status_text = part.partition("=")
        key, status_text = key.strip(), status_text.strip()
        if not sep or not key:
            logger.info("ignoring malformed X-Simulate-Failure pair %r", part)
            continue
        try:
            status = int(status_text)
        except ValueError:
            logger.info("ignoring X-Simulate-Failure pair with bad status %r", part)
            continue
        if status not in ALLOWED_STATUSES:
            logger.info("ignoring X-Simulate-Failure status %s (allowed: 429, 500, 502, 503)", status)
            continue
        if key == "*":
            wildcard = status
        elif key in key_ids:
            explicit[key] = status
        else:
            logger.info("ignoring X-Simulate-Failure for unknown key id %r", key)

    plan: dict[str, int] = {}
    for key_id in key_ids:
        if key_id in explicit:
            plan[key_id] = explicit[key_id]
        elif wildcard is not None:
            plan[key_id] = wildcard
    return plan
