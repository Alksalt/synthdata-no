"""SSB KLASS classification 131 (kommuner) snapshot loader.

The committed snapshot at src/synthdata_no/data/klass_131_snapshot.json
was fetched by scripts/fetch_klass_snapshot.py from:
  https://data.ssb.no/api/klass/v1/classifications/131
License: NLOD 2.0 / CC BY 4.0 — Statistics Norway (SSB)
Attribution: Statistics Norway (SSB), data.ssb.no/api/klass, classification 131 (Kommuner i Norge)

Never hand-write kommune codes — always regenerate the snapshot via the fetch script.
"""
from __future__ import annotations

import json
from functools import lru_cache
from importlib.resources import files
from typing import Optional

import numpy as np


@lru_cache(maxsize=1)
def _load_snapshot() -> dict:
    """Load and cache the committed KLASS snapshot."""
    data_path = files("synthdata_no.data").joinpath("klass_131_snapshot.json")
    with data_path.open(encoding="utf-8") as f:
        return json.load(f)


def valid_kommune_codes() -> list[str]:
    """Return list of all valid 4-digit kommune codes from the committed snapshot.

    Returns:
        Sorted list of 4-digit strings (e.g. ['0301', '1101', ...]).
    """
    snap = _load_snapshot()
    return [entry["code"] for entry in snap["kommuner"]]


def kommune_name(code: str) -> Optional[str]:
    """Return the Norwegian name for a 4-digit kommune code.

    Args:
        code: 4-digit kommune code (e.g. '0301').

    Returns:
        The kommune name (e.g. 'Oslo'), or None if the code is not in the snapshot.
    """
    snap = _load_snapshot()
    for entry in snap["kommuner"]:
        if entry["code"] == code:
            return entry["name"]
    return None


def random_kommune(
    rng: np.random.Generator,
    weights: Optional[dict[str, float]] = None,
) -> str:
    """Return a random valid kommune code.

    Args:
        rng: Seeded numpy Generator — mandatory for determinism.
        weights: Optional dict mapping kommune code → relative weight.
            Codes not in weights default to weight 1.0.
            Pass {code: 0.0} to exclude a code entirely.

    Returns:
        A 4-digit kommune code string.
    """
    codes = valid_kommune_codes()
    if weights is not None:
        w_arr = np.array([weights.get(c, 1.0) for c in codes], dtype=float)
        total = w_arr.sum()
        if total <= 0:
            raise ValueError("All weights are zero — cannot sample")
        probs = w_arr / total
        idx = rng.choice(len(codes), p=probs)
    else:
        idx = rng.integers(0, len(codes))
    return codes[int(idx)]
