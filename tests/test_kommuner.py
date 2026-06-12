"""Tests for synthdata_no.kommuner — SSB KLASS snapshot loader."""
from __future__ import annotations

import numpy as np
import pytest

from synthdata_no.kommuner import (
    random_kommune,
    valid_kommune_codes,
)


def test_snapshot_parses_and_returns_codes():
    codes = valid_kommune_codes()
    assert isinstance(codes, list)
    assert len(codes) >= 350, f"Expected ≥350 kommuner, got {len(codes)}"


def test_snapshot_contains_known_kommuner():
    codes = valid_kommune_codes()
    assert "0301" in codes, "Oslo (0301) not found"
    assert "5001" in codes, "Trondheim (5001) not found"
    assert "3216" in codes or any(c.startswith("32") for c in codes), (
        "No Viken-area codes found (expected 32xx series)"
    )


def test_snapshot_codes_are_4_digit_strings():
    codes = valid_kommune_codes()
    for c in codes:
        assert isinstance(c, str)
        assert len(c) == 4, f"Code {c!r} is not 4 digits"
        assert c.isdigit(), f"Code {c!r} is not all digits"


def test_random_kommune_returns_valid_code():
    codes = valid_kommune_codes()
    rng = np.random.default_rng(42)
    for _ in range(100):
        k = random_kommune(rng)
        assert k in codes, f"random_kommune returned unknown code: {k}"


def test_random_kommune_deterministic():
    a = [random_kommune(np.random.default_rng(7)) for _ in range(50)]
    b = [random_kommune(np.random.default_rng(7)) for _ in range(50)]
    assert a == b, "random_kommune is not deterministic"


def test_random_kommune_with_weights():
    codes = valid_kommune_codes()
    rng = np.random.default_rng(1)
    # Weight heavily toward Oslo
    weights = {c: 1000.0 if c == "0301" else 0.0001 for c in codes}
    results = [random_kommune(rng, weights=weights) for _ in range(50)]
    assert all(r == "0301" for r in results), (
        "Weighted random_kommune did not return Oslo (0301) when weighted 1000x"
    )


def test_snapshot_has_metadata():
    """The snapshot JSON must have date, source, and license header fields."""
    import json
    from importlib.resources import files
    data_path = files("synthdata_no.data").joinpath("klass_131_snapshot.json")
    with data_path.open() as f:
        snap = json.load(f)
    assert "date" in snap, "Snapshot missing 'date' field"
    assert "source" in snap, "Snapshot missing 'source' field"
    assert "license" in snap, "Snapshot missing 'license' field"
    assert "kommuner" in snap, "Snapshot missing 'kommuner' field"
