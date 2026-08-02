from __future__ import annotations

import hashlib
import math


def embed(text: str, dimensions: int = 64) -> list[float]:
    """Stable local embedding for zero-cost mock mode; not an LLM embedding API."""
    values = [0.0] * dimensions
    normalized = " ".join(text.casefold().split())
    for token in normalized.split() or [normalized]:
        digest = hashlib.blake2b(token.encode(), digest_size=16).digest()
        for offset, byte in enumerate(digest):
            values[(byte + offset * 17) % dimensions] += 1.0 if byte % 2 else -1.0
    norm = math.sqrt(sum(value * value for value in values)) or 1.0
    return [value / norm for value in values]


def cosine_score(left: list[float], right: list[float]) -> float:
    if len(left) != len(right):
        raise ValueError("embedding dimensions differ")
    return sum(a * b for a, b in zip(left, right, strict=True))
