"""Tests for synthdata_no.persons — Person dataclass + generator."""
from __future__ import annotations

import datetime

import numpy as np
import pytest
from faker import Faker

from synthdata_no.ids import is_synthetic_fnr, valid_fnr_checksum
from synthdata_no.kommuner import valid_kommune_codes
from synthdata_no.persons import Person, generate_person, generate_persons


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

def test_generate_person_deterministic():
    a = generate_person(seed=42)
    b = generate_person(seed=42)
    assert a == b, "generate_person must be deterministic given the same seed"


def test_generate_persons_deterministic():
    batch_a = generate_persons(20, seed=99)
    batch_b = generate_persons(20, seed=99)
    assert batch_a == batch_b


# ---------------------------------------------------------------------------
# Tenor-range guard: no identifier with month ≤ 12
# ---------------------------------------------------------------------------

def test_no_real_range_identifier():
    """CRITICAL: no generated person's identifier may have month ≤ 12."""
    persons = generate_persons(500, seed=77)
    for p in persons:
        month = int(p.fnr[2:4])
        assert month > 12, (
            f"Real-range identifier detected: {p.fnr} "
            f"(month={month} must be >12 for Tenor synthetic range)"
        )


def test_identifier_checksum_valid():
    persons = generate_persons(200, seed=5)
    for p in persons:
        assert valid_fnr_checksum(p.fnr), f"Checksum invalid for: {p.fnr}"


def test_identifier_is_synthetic():
    persons = generate_persons(100, seed=3)
    for p in persons:
        assert is_synthetic_fnr(p.fnr), f"Identifier not in synthetic range: {p.fnr}"


# ---------------------------------------------------------------------------
# D-number generation
# ---------------------------------------------------------------------------

def test_dnr_persons_have_day_offset():
    """Persons generated with dnr=True must have day+40 offset (day 41–71)."""
    persons = generate_persons(100, seed=11, dnr=True)
    for p in persons:
        day = int(p.fnr[0:2])
        assert 41 <= day <= 71, f"D-nr day {day} not in 41–71: {p.fnr}"
        month = int(p.fnr[2:4])
        assert 81 <= month <= 92, f"D-nr month {month} not in 81–92: {p.fnr}"


# ---------------------------------------------------------------------------
# Norwegian-locale sanity — guards the silent nb_NO→en_US trap
# ---------------------------------------------------------------------------

def test_never_constructs_faker_with_nb_NO():
    """Faker('nb_NO') silently falls back to en_US. We must never construct Faker with it.
    This test documents and enforces that persons.py uses 'no_NO' as the active locale."""
    import pathlib
    src = pathlib.Path(__file__).parent.parent / "src" / "synthdata_no" / "persons.py"
    content = src.read_text()
    # The active locale constant must be 'no_NO'
    assert "_FAKER_LOCALE = \"no_NO\"" in content or "_FAKER_LOCALE = 'no_NO'" in content, (
        "persons.py must define _FAKER_LOCALE = 'no_NO'"
    )
    # Faker must never be instantiated with 'nb_NO' as the first positional/keyword arg
    import re
    # Match Faker("nb_NO") or Faker('nb_NO') — instantiation patterns
    nb_no_instantiation = re.search(r'Faker\(["\']nb_NO["\']', content)
    assert nb_no_instantiation is None, (
        "persons.py must not construct Faker('nb_NO') — it silently falls back to en_US. "
        "Use 'no_NO' instead."
    )


def test_faker_nb_NO_trap_raises_attribute_error():
    """Documented trap: Faker('nb_NO') raises AttributeError — it is NOT a valid locale.
    In older Faker versions it fell back to en_US silently; in Faker 25+ it crashes.
    Either way, using 'nb_NO' is wrong. This test documents the error so it is never
    accidentally used. We assert 'no_NO' works and 'nb_NO' does NOT."""
    # 'nb_NO' must fail — either raise or silently fall back to en_US
    with pytest.raises((AttributeError, Exception)):
        Faker("nb_NO")

    # 'no_NO' must succeed and yield Norwegian-looking names
    faker_no = Faker("no_NO")
    faker_no.seed_instance(12345)
    names_no = [faker_no.name() for _ in range(20)]
    norwegian_indicators = {
        "hansen", "olsen", "larsen", "andersen", "nilsen", "berg", "haug",
        "eirik", "ingrid", "bjorn", "thor", "astrid", "gunnar", "sigrid",
        "anders", "kristian", "leif", "rolf", "silje", "hanne", "kari",
    }
    names_lower = " ".join(names_no).lower()
    assert any(ind in names_lower for ind in norwegian_indicators), (
        f"Faker('no_NO') does not seem to yield Norwegian names. Got: {names_no}. "
        "Check if the Faker locale 'no_NO' is still valid."
    )


# ---------------------------------------------------------------------------
# Person dataclass fields
# ---------------------------------------------------------------------------

def test_person_has_required_fields():
    p = generate_person(seed=1)
    assert isinstance(p, Person)
    assert isinstance(p.name, str) and p.name
    assert isinstance(p.fnr, str) and len(p.fnr) == 11
    assert isinstance(p.birth_date, datetime.date)
    assert p.sex in ("M", "F")
    assert isinstance(p.address, str) and p.address
    assert isinstance(p.postal_code, str) and p.postal_code
    assert isinstance(p.kommune, str) and len(p.kommune) == 4


def test_person_kommune_is_valid():
    valid_codes = set(valid_kommune_codes())
    persons = generate_persons(50, seed=55)
    for p in persons:
        assert p.kommune in valid_codes, f"Invalid kommune code: {p.kommune}"


def test_person_kommune_filter():
    """generate_person with kommune kwarg must always use that kommune."""
    for seed in range(10):
        p = generate_person(seed=seed, kommune="0301")
        assert p.kommune == "0301"


# ---------------------------------------------------------------------------
# Batch generation
# ---------------------------------------------------------------------------

def test_generate_persons_count():
    persons = generate_persons(100, seed=42)
    assert len(persons) == 100


def test_generate_persons_mix_of_sexes():
    persons = generate_persons(200, seed=42)
    sexes = {p.sex for p in persons}
    assert sexes == {"M", "F"}, "Expected both sexes in a 200-person batch"
