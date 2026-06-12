"""Synthetic Norwegian person generator.

Generates Person records with:
  - Tenor-range fnr/D-nr from ids.py (NEVER Faker.ssn())
  - Norwegian names and addresses from Faker locale 'no_NO'
    (note: 'nb_NO' does NOT exist as a Faker locale — it silently falls
     back to en_US; always use 'no_NO')
  - Valid kommune code from the committed KLASS snapshot

Determinism: all generators require an explicit seed or rng.
One seed → byte-identical output. No unseeded randomness on any path.
"""
from __future__ import annotations

import datetime
import random
from dataclasses import dataclass
from typing import Literal, Optional

import numpy as np
from faker import Faker

from synthdata_no.ids import synthetic_dnr, synthetic_fnr
from synthdata_no.kommuner import random_kommune

# Faker locale: MUST be 'no_NO'. 'nb_NO' does not exist in Faker and silently
# falls back to en_US — which would produce English names, not Norwegian.
_FAKER_LOCALE = "no_NO"

# Birth year range for generated persons (adults, working-age + elderly)
_BIRTH_YEAR_MIN = 1930
_BIRTH_YEAR_MAX = 2005


@dataclass(frozen=True)
class Person:
    """A synthetic Norwegian person record.

    All identifiers are in the Tenor synthetic range (month 81–92).
    No real persons can be derived from this data — identifiers are
    constructed, not drawn from any real register.
    """
    name: str
    fnr: str                  # 11-digit Tenor-range fødselsnummer or D-nr
    birth_date: datetime.date
    sex: Literal["M", "F"]
    address: str
    postal_code: str
    kommune: str              # 4-digit SSB kommune code


def _random_birth_date(rng: np.random.Generator) -> datetime.date:
    """Pick a random birth date in the adult range."""
    year = int(rng.integers(_BIRTH_YEAR_MIN, _BIRTH_YEAR_MAX + 1))
    month = int(rng.integers(1, 13))
    # Clamp day to valid range for the month/year
    import calendar
    max_day = calendar.monthrange(year, month)[1]
    day = int(rng.integers(1, max_day + 1))
    return datetime.date(year, month, day)


def generate_person(
    seed: Optional[int] = None,
    *,
    rng: Optional[np.random.Generator] = None,
    dnr: bool = False,
    kommune: Optional[str] = None,
) -> Person:
    """Generate a single synthetic Norwegian person.

    Exactly one of `seed` or `rng` must be provided for determinism.
    If `seed` is given, a fresh Generator is created from it.

    Args:
        seed: Integer seed — creates a new Generator internally.
        rng: Pre-seeded numpy Generator (takes precedence over seed).
        dnr: If True, generate a D-number (day+40 offset) instead of fnr.
        kommune: If given, pin the person to this 4-digit kommune code.

    Returns:
        A Person dataclass with all fields populated.
    """
    if rng is None:
        if seed is None:
            raise ValueError("Provide either seed or rng — unseeded generation is forbidden")
        rng = np.random.default_rng(seed)

    # Faker seeded via seed_instance for name/address only
    # We derive an int seed from the rng state so Faker output is deterministic
    faker_seed = int(rng.integers(0, 2**31))
    fake = Faker(_FAKER_LOCALE)
    fake.seed_instance(faker_seed)

    # Also seed stdlib random for any Faker internals that use it
    random.seed(faker_seed)

    birth_date = _random_birth_date(rng)
    sex: Literal["M", "F"] = "M" if rng.integers(0, 2) == 1 else "F"

    if dnr:
        fnr = synthetic_dnr(birth_date, sex, rng=rng)
    else:
        fnr = synthetic_fnr(birth_date, sex, rng=rng)

    name = fake.name()
    address = fake.street_address()
    postal_code = fake.postcode()
    kom = kommune if kommune is not None else random_kommune(rng)

    return Person(
        name=name,
        fnr=fnr,
        birth_date=birth_date,
        sex=sex,
        address=address,
        postal_code=postal_code,
        kommune=kom,
    )


def generate_persons(
    n: int,
    seed: int,
    *,
    dnr: bool = False,
    kommune: Optional[str] = None,
) -> list[Person]:
    """Generate a batch of n synthetic persons with a single seed.

    One seed → byte-identical list. Uses a single RNG to sequence all draws.

    Args:
        n: Number of persons to generate.
        seed: Integer seed — deterministic.
        dnr: If True, all persons get D-numbers.
        kommune: If given, all persons get this kommune code.

    Returns:
        List of Person objects.
    """
    rng = np.random.default_rng(seed)
    return [generate_person(rng=rng, dnr=dnr, kommune=kommune) for _ in range(n)]
