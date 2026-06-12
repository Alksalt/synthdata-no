"""Tests for synthdata_no.ids — Tenor synthetic fnr/D-nr generator.

All tests follow the plan F1 spec exactly.
"""
from __future__ import annotations

import datetime

import numpy as np
import pytest

from synthdata_no.ids import (
    fnr_birth_date,
    is_synthetic_fnr,
    synthetic_dnr,
    synthetic_fnr,
    valid_fnr_checksum,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

RNG = np.random.default_rng(0)
DOB_1990 = datetime.date(1990, 5, 17)  # 1900s birth year
DOB_2010 = datetime.date(2010, 3, 1)   # 2000s birth year
DOB_1970 = datetime.date(1970, 11, 4)  # 1900s birth year


# ---------------------------------------------------------------------------
# F1-a: month always in 81–92 for synthetic_fnr
# ---------------------------------------------------------------------------

def test_fnr_month_in_synthetic_range():
    rng = np.random.default_rng(42)
    for _ in range(200):
        fnr = synthetic_fnr(DOB_1990, "M", rng=rng)
        month_digits = int(fnr[2:4])
        assert 81 <= month_digits <= 92, f"Month out of synthetic range: {fnr}"


def test_fnr_month_in_synthetic_range_female():
    rng = np.random.default_rng(7)
    for _ in range(200):
        fnr = synthetic_fnr(DOB_1970, "F", rng=rng)
        month_digits = int(fnr[2:4])
        assert 81 <= month_digits <= 92, f"Month out of synthetic range: {fnr}"


# ---------------------------------------------------------------------------
# F1-b: D-nr — day in 41–71 AND month in 81–92
# ---------------------------------------------------------------------------

def test_dnr_day_in_synthetic_range():
    rng = np.random.default_rng(99)
    for _ in range(200):
        dnr = synthetic_dnr(DOB_1990, "M", rng=rng)
        day_digits = int(dnr[0:2])
        month_digits = int(dnr[2:4])
        assert 41 <= day_digits <= 71, f"D-nr day out of range: {dnr}"
        assert 81 <= month_digits <= 92, f"D-nr month out of range: {dnr}"


def test_dnr_female():
    rng = np.random.default_rng(123)
    for _ in range(200):
        dnr = synthetic_dnr(DOB_2010, "F", rng=rng)
        day_digits = int(dnr[0:2])
        month_digits = int(dnr[2:4])
        assert 41 <= day_digits <= 71
        assert 81 <= month_digits <= 92


# ---------------------------------------------------------------------------
# F1-c: checksum is valid for every generated id
# ---------------------------------------------------------------------------

def test_fnr_checksum_valid():
    rng = np.random.default_rng(1)
    for _ in range(300):
        fnr = synthetic_fnr(DOB_1990, "M", rng=rng)
        assert valid_fnr_checksum(fnr), f"Invalid checksum: {fnr}"


def test_dnr_checksum_valid():
    rng = np.random.default_rng(2)
    for _ in range(300):
        dnr = synthetic_dnr(DOB_1990, "F", rng=rng)
        assert valid_fnr_checksum(dnr), f"Invalid D-nr checksum: {dnr}"


# ---------------------------------------------------------------------------
# F1-d: un-offset variant is NEVER emitted (real-range fnr blocked)
# ---------------------------------------------------------------------------

def test_fnr_never_real_range():
    """Generated fnr must NOT have month in 01–12 (real range)."""
    rng = np.random.default_rng(5)
    for _ in range(500):
        fnr = synthetic_fnr(DOB_1990, "M", rng=rng)
        month_digits = int(fnr[2:4])
        assert month_digits > 12, f"Real-range month found: {fnr}"


def test_dnr_never_real_day_range():
    """D-nr day must NOT be 01–31 (real range)."""
    rng = np.random.default_rng(6)
    for _ in range(500):
        dnr = synthetic_dnr(DOB_1970, "F", rng=rng)
        day_digits = int(dnr[0:2])
        assert day_digits > 31, f"Real-range day found: {dnr}"


# ---------------------------------------------------------------------------
# F1-e: sex parity (3rd individ digit: even=F, odd=M)
# ---------------------------------------------------------------------------

def test_fnr_sex_parity_male():
    rng = np.random.default_rng(10)
    for _ in range(200):
        fnr = synthetic_fnr(DOB_1990, "M", rng=rng)
        third_individ_digit = int(fnr[8])  # 0-indexed: positions 6,7,8 = individnummer
        assert third_individ_digit % 2 == 1, f"Male fnr has even 3rd individ digit: {fnr}"


def test_fnr_sex_parity_female():
    rng = np.random.default_rng(11)
    for _ in range(200):
        fnr = synthetic_fnr(DOB_1990, "F", rng=rng)
        third_individ_digit = int(fnr[8])
        assert third_individ_digit % 2 == 0, f"Female fnr has odd 3rd individ digit: {fnr}"


# ---------------------------------------------------------------------------
# F1-f: century/individnummer range consistent with birth year
# ---------------------------------------------------------------------------

def test_individ_range_1990s():
    """1990: individnummer must be 000–499 (→ 1900–1999)."""
    rng = np.random.default_rng(20)
    for _ in range(200):
        fnr = synthetic_fnr(DOB_1990, "M", rng=rng)
        individ = int(fnr[6:9])
        # 1990 → 1900s: individ 000–499 (only range unambiguously 1900s)
        # Also 900–999 → 1940–1999, so 1990 can use both ranges
        assert individ <= 499 or 900 <= individ <= 999, (
            f"1990 birth: individ {individ} outside valid ranges for 1900s: {fnr}"
        )


def test_individ_range_2010s():
    """2010: individnummer must be in 500–749 or 750–899 (→ 2000–2039)."""
    rng = np.random.default_rng(21)
    for _ in range(200):
        fnr = synthetic_fnr(DOB_2010, "M", rng=rng)
        individ = int(fnr[6:9])
        assert 500 <= individ <= 899, (
            f"2010 birth: individ {individ} outside valid ranges for 2000s: {fnr}"
        )


# ---------------------------------------------------------------------------
# F1-g: reject-loop covered (a seed known to hit k=10 path still produces output)
# This tests that the generator doesn't crash when k1 or k2 == 10 (must retry)
# ---------------------------------------------------------------------------

def test_reject_loop_does_not_crash():
    """Generator must produce valid output even for births that may hit k=10."""
    # Try many births to ensure the reject path is exercised and handled
    problematic_dates = [
        datetime.date(1990, 1, 1),
        datetime.date(1985, 6, 15),
        datetime.date(1960, 12, 31),
        datetime.date(2000, 7, 4),
        datetime.date(1940, 3, 22),
    ]
    rng = np.random.default_rng(99999)
    for dob in problematic_dates:
        for sex in ("M", "F"):
            for _ in range(20):
                fnr = synthetic_fnr(dob, sex, rng=rng)
                assert valid_fnr_checksum(fnr)


# ---------------------------------------------------------------------------
# F1-h: seed determinism over 1000 ids
# ---------------------------------------------------------------------------

def test_fnr_determinism_1000():
    dob = datetime.date(1985, 3, 15)
    ids_a = [synthetic_fnr(dob, "M", rng=np.random.default_rng(42)) for _ in range(1000)]
    ids_b = [synthetic_fnr(dob, "M", rng=np.random.default_rng(42)) for _ in range(1000)]
    assert ids_a == ids_b, "Same seed must produce identical output"


def test_dnr_determinism_1000():
    dob = datetime.date(1975, 8, 20)
    ids_a = [synthetic_dnr(dob, "F", rng=np.random.default_rng(77)) for _ in range(1000)]
    ids_b = [synthetic_dnr(dob, "F", rng=np.random.default_rng(77)) for _ in range(1000)]
    assert ids_a == ids_b, "Same seed must produce identical output"


# ---------------------------------------------------------------------------
# F1-i: is_synthetic_fnr correctly classifies
# ---------------------------------------------------------------------------

def test_is_synthetic_fnr_true():
    rng = np.random.default_rng(88)
    for _ in range(100):
        fnr = synthetic_fnr(DOB_1990, "M", rng=rng)
        assert is_synthetic_fnr(fnr), f"Generated fnr not classified as synthetic: {fnr}"


def test_is_synthetic_fnr_true_dnr():
    rng = np.random.default_rng(89)
    for _ in range(100):
        dnr = synthetic_dnr(DOB_1990, "F", rng=rng)
        assert is_synthetic_fnr(dnr), f"Generated D-nr not classified as synthetic: {dnr}"


def test_is_synthetic_fnr_false_for_non_digit():
    assert not is_synthetic_fnr("abc12345678")
    assert not is_synthetic_fnr("12345678901")  # valid checksum structure but real-range
    assert not is_synthetic_fnr("")


# ---------------------------------------------------------------------------
# F1-j: fnr_birth_date round-trips correctly
# ---------------------------------------------------------------------------

def test_fnr_birth_date_round_trip():
    test_dates = [DOB_1990, DOB_2010, DOB_1970]
    rng = np.random.default_rng(55)
    for dob in test_dates:
        fnr = synthetic_fnr(dob, "M", rng=rng)
        recovered = fnr_birth_date(fnr)
        assert recovered == dob, f"Birth date round-trip failed for {dob}: got {recovered} from {fnr}"


def test_dnr_birth_date_round_trip():
    rng = np.random.default_rng(56)
    for dob in [DOB_1990, DOB_1970]:
        dnr = synthetic_dnr(dob, "F", rng=rng)
        recovered = fnr_birth_date(dnr)
        assert recovered == dob, f"D-nr birth date round-trip failed for {dob}: got {recovered} from {dnr}"


# ---------------------------------------------------------------------------
# F1-k: length and digit-only
# ---------------------------------------------------------------------------

def test_fnr_length_and_digits():
    rng = np.random.default_rng(33)
    for _ in range(100):
        fnr = synthetic_fnr(DOB_1990, "M", rng=rng)
        assert len(fnr) == 11, f"fnr wrong length: {fnr}"
        assert fnr.isdigit(), f"fnr not all digits: {fnr}"
