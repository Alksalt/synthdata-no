"""Tenor synthetic fødselsnummer / D-nummer generator.

Every generated identifier sits in the Tenor synthetic range:
  - month + 80  (months 81–92)
  - D-numbers additionally: day + 40
  - mod-11 control digits computed AFTER offsets

Checksum logic vendored from the omsorgsradar project (core/anonymize/pii.py).
(project: omsorgsradar — MIT-compatible; vendored with attribution per DECISIONS.md)

Individnummer century ranges (unchanged in synthetic range — offsets only touch MM/DD):
  000–499 → 1900–1999
  500–749 → 1854–1899 (yy 54–99) and 2000–2039 (yy 00–53)  (YY disambiguates)
  750–899 → 2000–2039
  900–999 → 1940–1999

Source: Skatteetaten official fnr specification + Wikipedia «National identification number (Norway)».
Lower bound 1854 confirmed: yy=54 with individ 500–749 → 1854.
900–999 covers 1940–1999 ONLY (not 2000+); 2000–2039 births use 500–749 and 750–899.

Sex parity: 3rd individnummer digit even=F, odd=M.
~17% of stems yield k1 or k2 == 10 → discard-and-regenerate loop.
"""
from __future__ import annotations

import datetime
from typing import Literal

import numpy as np

# ---------------------------------------------------------------------------
# Vendored checksum — omsorgsradar/src/omsorgsradar/core/anonymize/pii.py
# Attribution: Oleksandr Altukhov / omsorgsradar (2026-06-11), MIT-compatible.
# Do NOT re-derive; if the source changes, re-vendor with attribution.
# ---------------------------------------------------------------------------

_FNR_K1_W = [3, 7, 6, 1, 8, 9, 4, 5, 2]
_FNR_K2_W = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]


def _control_digit(digits: list[int], weights: list[int]) -> int | None:
    s = sum(d * w for d, w in zip(digits, weights))
    k = 11 - (s % 11)
    if k == 11:
        return 0
    if k == 10:
        return None  # reject — caller must try next individnummer
    return k


def valid_fnr_checksum(fnr: str) -> bool:
    """Return True if fnr/D-nr has valid mod-11 control digits."""
    if len(fnr) != 11 or not fnr.isdigit():
        return False
    d = [int(c) for c in fnr]
    k1 = _control_digit(d[:9], _FNR_K1_W)
    k2 = _control_digit(d[:10], _FNR_K2_W)
    return k1 is not None and k2 is not None and k1 == d[9] and k2 == d[10]


def append_fnr_control_digits(stem9: str) -> str:
    """Append valid k1+k2 to a 9-digit stem (DDMMYY+individ).
    Raises ValueError if stem yields invalid k1 or k2 (caller must retry)."""
    d = [int(c) for c in stem9]
    k1 = _control_digit(d, _FNR_K1_W)
    if k1 is None:
        raise ValueError(f"stem {stem9!r} yields invalid k1; try another individnummer")
    k2 = _control_digit(d + [k1], _FNR_K2_W)
    if k2 is None:
        raise ValueError(f"stem {stem9!r} yields invalid k2; try another individnummer")
    return stem9 + str(k1) + str(k2)

# ---------------------------------------------------------------------------
# End of vendored section
# ---------------------------------------------------------------------------


def _century_individ_ranges(year: int) -> list[tuple[int, int]]:
    """Return valid individnummer ranges for the given 4-digit birth year.

    Ranges per Skatteetaten official spec:
      000–499 → 1900–1999
      900–999 → 1940–1999
      500–749 → 1854–1899 (yy 54–99) and 2000–2039 (yy 00–53)
      750–899 → 2000–2039

    Lower bound 1854: yy=54 with individ 500–749 unambiguously means 1854.
    """
    ranges: list[tuple[int, int]] = []
    # 000–499 → 1900–1999
    if 1900 <= year <= 1999:
        ranges.append((0, 499))
    # 900–999 → 1940–1999 (Skatteetaten spec: only for 1940–1999, NOT 2000+)
    if 1940 <= year <= 1999:
        ranges.append((900, 999))
    # 500–749 → 1854–1899 (lower bound 1854, not 1855)
    if 1854 <= year <= 1899:
        ranges.append((500, 749))
    if 2000 <= year <= 2039:
        ranges.append((500, 749))
    # 750–899 → 2000–2039
    if 2000 <= year <= 2039:
        ranges.append((750, 899))
    if not ranges:
        raise ValueError(f"No valid individnummer range for year {year}")
    return ranges


def _pick_individnummer(
    year: int,
    sex: Literal["M", "F"],
    rng: np.random.Generator,
) -> int:
    """Pick an individnummer consistent with century and sex parity.
    Sex: F → 3rd individ digit even (0,2,4,6,8); M → odd (1,3,5,7,9).
    """
    ranges = _century_individ_ranges(year)
    # Collect all candidates matching sex parity from all valid ranges
    candidates: list[int] = []
    for lo, hi in ranges:
        for n in range(lo, hi + 1):
            third_digit = n % 10
            if sex == "F" and third_digit % 2 == 0:
                candidates.append(n)
            elif sex == "M" and third_digit % 2 == 1:
                candidates.append(n)
    return int(rng.choice(candidates))


def _build_fnr(
    birth_date: datetime.date,
    sex: Literal["M", "F"],
    *,
    rng: np.random.Generator,
    dnr: bool = False,
) -> str:
    """Internal builder for fnr or D-nr.

    Applies offsets, then loops over individnummer candidates until
    a valid checksum is found (handles the ~17% k=10 reject rate).
    """
    day = birth_date.day
    month = birth_date.month
    year = birth_date.year
    yy = year % 100

    # Apply Tenor offsets
    month_enc = month + 80            # synthetic marker: 81–92
    if dnr:
        day_enc = day + 40            # D-number additional offset: 41–71
    else:
        day_enc = day

    day_str = f"{day_enc:02d}"
    month_str = f"{month_enc:02d}"
    year_str = f"{yy:02d}"
    date_stem = day_str + month_str + year_str  # 6 digits

    # Retry until we get a checksum-valid individnummer (handles ~17% rejects)
    max_attempts = 200
    for _ in range(max_attempts):
        individ = _pick_individnummer(year, sex, rng)
        individ_str = f"{individ:03d}"
        stem9 = date_stem + individ_str
        try:
            return append_fnr_control_digits(stem9)
        except ValueError:
            continue  # k1 or k2 == 10, try another individnummer

    raise RuntimeError(
        f"Could not find valid individnummer after {max_attempts} attempts "
        f"for birth_date={birth_date}, sex={sex}, dnr={dnr}"
    )


def synthetic_fnr(
    birth_date: datetime.date,
    sex: Literal["M", "F"],
    *,
    rng: np.random.Generator,
) -> str:
    """Generate a Tenor-range synthetic fødselsnummer.

    Args:
        birth_date: The birth date. Month will be offset +80 (Tenor convention).
        sex: 'M' for male (odd 3rd individ digit), 'F' for female (even).
        rng: Seeded numpy Generator — mandatory, no default entropy.

    Returns:
        11-digit string with valid mod-11 control digits and month in 81–92.
    """
    return _build_fnr(birth_date, sex, rng=rng, dnr=False)


def synthetic_dnr(
    birth_date: datetime.date,
    sex: Literal["M", "F"],
    *,
    rng: np.random.Generator,
) -> str:
    """Generate a Tenor-range synthetic D-nummer (stacks both offsets: day+40, month+80).

    Args:
        birth_date: The birth date. Day offset +40, month offset +80.
        sex: 'M' or 'F'.
        rng: Seeded numpy Generator — mandatory.

    Returns:
        11-digit string with valid mod-11 control digits, day in 41–71, month in 81–92.
    """
    return _build_fnr(birth_date, sex, rng=rng, dnr=True)


def is_synthetic_fnr(value: str) -> bool:
    """Return True if value is an 11-digit fnr/D-nr with month in 81–92 (Tenor range).

    Checks:
      1. Exactly 11 digits.
      2. Month field (digits 2–3, 0-indexed) in 81–92.
      3. Valid mod-11 checksum.
    """
    if not isinstance(value, str) or len(value) != 11 or not value.isdigit():
        return False
    month = int(value[2:4])
    if not (81 <= month <= 92):
        return False
    return valid_fnr_checksum(value)


def fnr_birth_date(value: str) -> datetime.date:
    """Extract the birth date from a synthetic fnr or D-nr.

    Reverses the Tenor offsets: month -= 80, and for D-nr, day -= 40.
    Disambiguates century using individnummer ranges.

    Args:
        value: An 11-digit synthetic fnr or D-nr.

    Returns:
        The birth date.

    Raises:
        ValueError: If value is not a valid synthetic fnr/D-nr.
    """
    if not isinstance(value, str) or len(value) != 11 or not value.isdigit():
        raise ValueError(f"Not a valid 11-digit fnr/D-nr: {value!r}")

    day_enc = int(value[0:2])
    month_enc = int(value[2:4])
    yy = int(value[4:6])
    individ = int(value[6:9])

    # Reverse month offset
    if not (81 <= month_enc <= 92):
        raise ValueError(f"Month {month_enc} not in Tenor synthetic range 81–92")
    month = month_enc - 80

    # Reverse day offset (D-nr has day 41–71)
    if 41 <= day_enc <= 71:
        day = day_enc - 40
    elif 1 <= day_enc <= 31:
        day = day_enc
    else:
        raise ValueError(f"Day {day_enc} out of expected range")

    # Disambiguate century from individnummer
    # Source: Skatteetaten official fnr spec
    # 000–499 → 1900–1999
    # 500–749 → 2000–2039 (yy 00–53) or 1854–1899 (yy 54–99); yy 40–53 is ambiguous/unauthorized
    # 750–899 → 2000–2039
    # 900–999 → 1940–1999
    if 0 <= individ <= 499:
        year = 1900 + yy
    elif 500 <= individ <= 749:
        if yy <= 39:
            year = 2000 + yy
        elif yy >= 54:
            year = 1800 + yy
        else:
            # yy 40–53 with individ 500–749: would map to 1840–1853 (never generated)
            # or could be 2040–2053 (outside authorized range). This is ambiguous
            # and no valid Tenor synthetic fnr should exist here.
            raise ValueError(
                f"Cannot disambiguate century for individ={individ}, yy={yy:02d}: "
                f"individ range 500–749 with yy 40–53 is ambiguous "
                f"(1840–1853 is pre-spec; 2040–2053 is outside the 2000–2039 range). "
                "This is not a valid Tenor synthetic fnr."
            )
    elif 750 <= individ <= 899:
        year = 2000 + yy
    else:  # 900–999 → 1940–1999
        year = 1900 + yy

    return datetime.date(year, month, day)
