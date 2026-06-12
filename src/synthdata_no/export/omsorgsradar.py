"""omsorgsradar brfss-demo fixture emitter.

Produces a synthetic microdata fixture that exactly matches the brfss-demo contract
used by omsorgsradar's anonymize pipeline:

    Columns:
        state   (str)   — 4-digit kommune code (KLASS-131); column NAME kept as "state"
                          to avoid ANY edit to the omsorgsradar engine.
        age     (int)   — integer, 18–94 inclusive
        sex     (int)   — 1 (M) or 2 (F)
        diabetes (int)  — 0 or 1 (CPT-driven)
        notes   (str)   — free text; contains exactly 2 planted Tenor-range fnr
                          + 1 phone-like number

    Rows: 600
    Seed: 42 (documented — one seed → byte-identical output)

Planted PII pattern mirrors the original brfss-demo make_fixture.py pattern
(commit-safe filler rows + two fnr-bearing rows + one phone-bearing row),
but ALL identifiers are in the Tenor synthetic range (month 81–92 per synthdata-no spec).

    Row 0:  «pasient <fnr1> oppfølging»
    Row 1:  «tlf 91123456; fnr <fnr2>»  ← the phone-like number is a static filler
    Row 2+: «rutinekontroll»

The two planted fnr are Tenor-range (is_synthetic_fnr() returns True for both).
Row 1 also contains «91123456» — the same phone-like string as the original fixture —
which omsorgsradar's NO_TELEFON recognizer detects. This tests that the anonymize
gate fires on both entity types.

No real persons; safe to commit. NOT for statistical inference.
"""
from __future__ import annotations

import datetime
from pathlib import Path
from typing import Union

import numpy as np
import pandas as pd

from synthdata_no.ids import synthetic_fnr, is_synthetic_fnr
from synthdata_no.tabular import generate_table, _DEFAULT_CPT_TJENESTE_BRUK

# ---------------------------------------------------------------------------
# Diabetes CPT — mapped onto the brfss-demo "diabetes" column (0/1)
# Same approximate defaults as tjeneste_bruk; labelled non-representative.
# ---------------------------------------------------------------------------

_DIABETES_CPT = {
    "18-44": {"1": [0.90, 0.10], "2": [0.90, 0.10]},
    "45-64": {"1": [0.70, 0.30], "2": [0.70, 0.30]},
    "65-95": {"1": [0.55, 0.45], "2": [0.55, 0.45]},
}


def write_brfss_shaped_fixture(
    out_path: Union[str, Path],
    seed: int = 42,
) -> pd.DataFrame:
    """Emit a brfss-demo-shaped fixture CSV to out_path.

    Args:
        out_path: Destination CSV path. Parent directory is created if missing.
        seed: Integer seed (default 42). One seed → byte-identical output.

    Returns:
        The generated DataFrame (600 rows).

    Column schema (exact contract):
        state    str   4-digit KLASS-131 kommune code
        age      int   18–94
        sex      int   1 or 2
        diabetes int   0 or 1
        notes    str   free text; rows 0–1 carry planted Tenor-range fnr;
                       row 1 also contains phone-like «91123456»

    Planted PII:
        - Exactly 2 Tenor-range fnr (is_synthetic_fnr() == True for both)
        - 1 phone-like number «91123456» in row 1 (static filler — not a real number)
        - All remaining rows: «rutinekontroll»
    """
    N = 600
    config = {
        "columns": {
            "diabetes": {
                "type": "cpt",
                "categories": [0, 1],
                "cpt": _DIABETES_CPT,
            }
        },
        "planted_fnr_count": 0,  # we handle notes manually below
    }

    df = generate_table(config, n=N, seed=seed)

    # Clamp age to 18–94 (brfss contract upper bound is 94)
    df["age"] = df["age"].clip(18, 94)

    # Generate exactly 2 Tenor-range fnr using a seeded sub-rng for reproducibility
    fnr_rng = np.random.default_rng(seed + 1_000_000)

    fnr1 = synthetic_fnr(datetime.date(1990, 1, 15), "M", rng=fnr_rng)
    fnr2 = synthetic_fnr(datetime.date(1962, 3, 22), "F", rng=fnr_rng)

    assert is_synthetic_fnr(fnr1), f"fnr1 not in Tenor range: {fnr1}"
    assert is_synthetic_fnr(fnr2), f"fnr2 not in Tenor range: {fnr2}"

    # Notes column: mirror the original make_fixture.py PII pattern
    notes = ["rutinekontroll"] * N
    notes[0] = f"pasient {fnr1} oppfølging"
    notes[1] = f"tlf 91123456; fnr {fnr2}"

    df["notes"] = notes

    # Reorder columns to match exact contract: state, age, sex, diabetes, notes
    # "state" is what generate_table calls "kommune" — rename here
    df = df.rename(columns={"kommune": "state"})
    df = df[["state", "age", "sex", "diabetes", "notes"]]

    # Enforce dtypes per contract
    df["state"] = df["state"].astype(str)
    df["age"] = df["age"].astype(int)
    df["sex"] = df["sex"].astype(int)
    df["diabetes"] = df["diabetes"].astype(int)
    df["notes"] = df["notes"].astype(str)

    # Write CSV
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out, index=False)

    return df
