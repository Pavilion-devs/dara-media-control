from __future__ import annotations

import secrets
import time


_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def ulid() -> str:
    """Return a dependency-free, lexicographically sortable ULID."""
    value = (int(time.time_ns() // 1_000_000) << 80) | int.from_bytes(
        secrets.token_bytes(10),
        "big",
    )
    encoded = ["0"] * 26
    for index in range(25, -1, -1):
        encoded[index] = _CROCKFORD[value & 31]
        value >>= 5
    return "".join(encoded)


def new_id(prefix: str) -> str:
    return f"{prefix}_{ulid()}"
