"""Time-sortable identifiers and content hashing (doc 04 §1, doc 03 §13).

We use a UUIDv7-style scheme: a millisecond timestamp prefix plus randomness, rendered
as a canonical UUID string. This gives lexicographically sortable ids that approximate
total event order without requiring Python 3.14's ``uuid7``.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import uuid
from typing import Any


def new_id() -> str:
    """Return a time-sortable UUIDv7-style identifier as a string."""
    unix_ms = int(time.time() * 1000) & 0xFFFFFFFFFFFF  # 48 bits
    rand_a = int.from_bytes(os.urandom(2), "big") & 0x0FFF  # 12 bits
    rand_b = int.from_bytes(os.urandom(8), "big")
    # Layout per RFC 9562 v7: time(48) | ver(4)=7 | rand_a(12) | var(2) | rand_b(62)
    value = (unix_ms << 80) | (0x7 << 76) | (rand_a << 64)
    value |= (0b10 << 62) | (rand_b & ((1 << 62) - 1))
    return str(uuid.UUID(int=value & ((1 << 128) - 1)))


def content_hash(data: Any) -> str:
    """Stable sha256 of arbitrary JSON-serializable content (hex, prefixed)."""
    if isinstance(data, (bytes, bytearray)):
        digest = hashlib.sha256(bytes(data)).hexdigest()
    else:
        encoded = json.dumps(data, sort_keys=True, separators=(",", ":"), default=str)
        digest = hashlib.sha256(encoded.encode("utf-8")).hexdigest()
    return f"sha256:{digest}"
