"""Tabular synthetic health data generator for omsorgsradar and related consumers.

Generates a synthetic microdata table with realistic per-kommune age/sex marginals
drawn from a committed SSB 07459 snapshot, plus configurable correlated columns
via conditional probability tables (CPTs).

Determinism: all generators require an explicit seed. One seed → byte-identical output.
No unseeded randomness on any code path.

License: MIT
Source: Statistics Norway (SSB), CC BY 4.0 (snapshot only — not embedded in generated data).

Honesty framing: generated records represent NO REAL PERSONS, carry no re-identification
risk by construction, and are NOT suitable for statistical inference. Default CPT values
are approximate KOSTRA-aggregate-informed defaults and are labelled non-representative.
"""
from __future__ import annotations

import json
from functools import lru_cache
from importlib.resources import files
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from synthdata_no.ids import synthetic_fnr, is_synthetic_fnr
from synthdata_no.kommuner import valid_kommune_codes

# ---------------------------------------------------------------------------
# Age bands for CPT binning
# ---------------------------------------------------------------------------

# Closed intervals: [low, high]
_AGE_BANDS: list[tuple[int, int]] = [
    (18, 44),
    (45, 64),
    (65, 95),
]

_BAND_LABELS = ["18-44", "45-64", "65-95"]


def _age_band_label(age: int) -> str:
    """Map a scalar age to its band label."""
    for (lo, hi), label in zip(_AGE_BANDS, _BAND_LABELS):
        if lo <= age <= hi:
            return label
    return _BAND_LABELS[-1]  # clamp to last band


# ---------------------------------------------------------------------------
# Default CPTs — documented as approximate, KOSTRA-aggregate-informed defaults.
# These are NOT representative of any real population; labelled accordingly.
#
# Structure: {column_name: {age_band: {sex_str: probability_vector}}}
#   where probability_vector is over the column's categories in order.
#
# "sex_str" is "1" (M) or "2" (F) — mirrors SSB sex coding.
# ---------------------------------------------------------------------------

# tjeneste_bruk: binary (0=no service, 1=using service)
# Approximate defaults: ~10% in 18-44, ~30% in 45-64, ~50% in 65-95.
# NOT representative; KOSTRA-aggregate-informed; labelled non-representative.
_DEFAULT_CPT_TJENESTE_BRUK: dict[str, dict[str, list[float]]] = {
    "18-44": {"1": [0.90, 0.10], "2": [0.90, 0.10]},
    "45-64": {"1": [0.70, 0.30], "2": [0.70, 0.30]},
    "65-95": {"1": [0.50, 0.50], "2": [0.50, 0.50]},
}

# diagnosekategori: 4 categories (1–4 encoded as indices 0–3)
# Approximate defaults for elder-care population.
# NOT representative; KOSTRA-aggregate-informed; labelled non-representative.
_DEFAULT_CPT_DIAGNOSEKATEGORI: dict[str, dict[str, list[float]]] = {
    "18-44": {"1": [0.40, 0.30, 0.20, 0.10], "2": [0.40, 0.30, 0.20, 0.10]},
    "45-64": {"1": [0.30, 0.30, 0.25, 0.15], "2": [0.30, 0.30, 0.25, 0.15]},
    "65-95": {"1": [0.20, 0.25, 0.30, 0.25], "2": [0.25, 0.30, 0.25, 0.20]},
}

# Default column specs (tjeneste_bruk and diagnosekategori)
# categories lists the actual output values in order matching the CPT probability vector.
_DEFAULT_COLUMN_SPECS: dict[str, dict[str, Any]] = {
    "tjeneste_bruk": {
        "type": "cpt",
        "categories": [0, 1],  # 0=no, 1=yes
        "cpt": _DEFAULT_CPT_TJENESTE_BRUK,
        "description": (
            "Binary tjeneste_bruk. Approximate KOSTRA-aggregate-informed defaults: "
            "~10% age 18-44, ~30% age 45-64, ~50% age 65-95. NOT representative."
        ),
    },
    "diagnosekategori": {
        "type": "cpt",
        "categories": [1, 2, 3, 4],  # 4 categories
        "cpt": _DEFAULT_CPT_DIAGNOSEKATEGORI,
        "description": (
            "Diagnosekategori (1–4). Approximate KOSTRA-aggregate-informed defaults. "
            "NOT representative of any real diagnostic distribution."
        ),
    },
}


# ---------------------------------------------------------------------------
# Snapshot loader
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def _load_snapshot() -> pd.DataFrame:
    """Load the committed SSB 07459 parquet snapshot (cached after first load).

    Returns a DataFrame with columns: kommune (str), age (int), sex (int), count (int).
    """
    data_dir = files("synthdata_no.data")
    snap_path = data_dir.joinpath("ssb_07459_snapshot.parquet")
    # importlib.resources returns a PosixPath in dev-mode installs; use str() for pyarrow
    df = pd.read_parquet(str(snap_path))
    return df


def _build_weight_arrays(
    snapshot: pd.DataFrame,
    kommune_subset: list[str] | None,
) -> tuple[list[str], np.ndarray, dict[str, dict[int, np.ndarray]], list[int]]:
    """Pre-compute sampling structures from the snapshot.

    Returns:
        (commune_list, commune_weights, age_sex_weights_by_kommune)

        commune_list: sorted list of kommune codes in scope
        commune_weights: 1-D array of aggregate population by kommune (for commune sampling)
        age_sex_weights_by_kommune:
            {kommune: {sex_int: age_prob_array (length 78)}}
            where age_prob_array[i] = P(age=18+i | sex, kommune)
    """
    if kommune_subset is not None:
        valid = set(valid_kommune_codes())
        unknown = set(kommune_subset) - valid
        if unknown:
            raise ValueError(
                f"Unknown kommune codes (not in KLASS snapshot): {sorted(unknown)}"
            )
        snap = snapshot[snapshot["kommune"].isin(kommune_subset)].copy()
        if snap.empty or snap["count"].sum() == 0:
            raise ValueError(
                f"Requested kommune_subset produced an empty snapshot slice — "
                f"codes may be valid KLASS codes but absent from SSB 07459 data."
            )
    else:
        snap = snapshot.copy()

    # Commune weights
    commune_totals = snap.groupby("kommune")["count"].sum().sort_index()
    commune_list = list(commune_totals.index)
    commune_weights = commune_totals.values.astype(float)

    # Age range covered by snapshot: 18–95 (78 ages)
    ages = sorted(snap["age"].unique())

    # Per-kommune, per-sex conditional age distribution
    age_sex_weights: dict[str, dict[int, np.ndarray]] = {}
    for kommune, grp in snap.groupby("kommune"):
        age_sex_weights[str(kommune)] = {}
        for sex in [1, 2]:
            sex_grp = grp[grp["sex"] == sex].sort_values("age")
            counts = sex_grp.set_index("age").reindex(ages, fill_value=0)["count"].values.astype(float)
            total = counts.sum()
            if total > 0:
                age_sex_weights[str(kommune)][sex] = counts / total
            else:
                # Fallback: uniform
                age_sex_weights[str(kommune)][sex] = np.ones(len(ages)) / len(ages)

    return commune_list, commune_weights, age_sex_weights, ages


def _apply_cpt(
    age: int,
    sex: int,
    cpt: dict[str, dict[str, list[float]]],
    categories: list[Any],
    rng: np.random.Generator,
) -> Any:
    """Draw one value from the CPT for the given age and sex."""
    band = _age_band_label(age)
    sex_str = str(sex)
    prob_vector = cpt.get(band, cpt[_BAND_LABELS[-1]]).get(sex_str, list(cpt.values())[0].get(sex_str))
    # Normalise to handle minor float drift
    probs = np.array(prob_vector, dtype=float)
    probs = probs / probs.sum()
    choice_idx = int(rng.choice(len(categories), p=probs))
    return categories[choice_idx]


def _generate_notes_column(
    n: int,
    rng: np.random.Generator,
    planted_count: int,
    birth_dates: list | None = None,
) -> list[str]:
    """Generate a notes column with `planted_count` Tenor-range fnr planted in filler text.

    Each planted note looks like: «rutinekontroll <fnr> oppfølging».
    Remaining rows are «rutinekontroll».

    Args:
        n: Total number of rows.
        rng: Seeded numpy Generator.
        planted_count: Number of rows to carry a planted fnr.
        birth_dates: Optional list of (birth_date, sex) tuples to use for planted fnr.
            If None, generates with fixed birth dates.
    """
    import datetime

    notes = ["rutinekontroll"] * n

    # Deterministic planted positions: first `planted_count` rows
    planted_positions = list(range(planted_count))

    # Deterministic birth dates for planted fnr (if not provided)
    _fixed_dates = [
        (datetime.date(1990, 1, 15), "M"),
        (datetime.date(1962, 3, 22), "F"),
        (datetime.date(1975, 6, 8), "M"),
    ]

    for i, pos in enumerate(planted_positions):
        if birth_dates is not None and i < len(birth_dates):
            bd, sx = birth_dates[i]
        else:
            bd, sx = _fixed_dates[i % len(_fixed_dates)]
        fnr = synthetic_fnr(bd, sx, rng=rng)
        notes[pos] = f"rutinekontroll {fnr} oppfølging"

    return notes


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def generate_table(
    config: dict[str, Any],
    n: int,
    seed: int,
) -> pd.DataFrame:
    """Generate a synthetic tabular dataset with realistic Norwegian marginals.

    Args:
        config: Column configuration dict. Top-level keys:
            - "kommune_subset" (list[str] | None): restrict to these communes (KLASS codes).
            - "columns" (dict): column specs; if absent, defaults (tjeneste_bruk +
              diagnosekategori) are used. Each spec:
                {"type": "cpt",
                 "categories": [...],
                 "cpt": {age_band: {sex_str: prob_vector}}}
            - "planted_fnr_count" (int): number of rows with a planted Tenor fnr in a
              synthetic "notes" column (default 0; column omitted if 0).
        n: Number of rows to generate.
        seed: Integer seed for numpy default_rng. One seed → byte-identical output.

    Returns:
        pandas.DataFrame with columns:
            kommune (str, 4-digit KLASS code)
            age     (int, 18–95)
            sex     (int, 1=M / 2=F)
            <configured columns> (each driven by its CPT)
            [notes (str)] — only present when planted_fnr_count > 0

    Raises:
        ValueError: If unknown kommune codes are passed or config is malformed.

    Notes:
        - All values in the snapshot are aggregate counts; no individual-level data
          is fetched or embedded.
        - Default CPTs (tjeneste_bruk, diagnosekategori) are approximate
          KOSTRA-aggregate-informed defaults and are NOT representative of any real
          population. Do not use for statistical inference.
    """
    rng = np.random.default_rng(seed)
    snapshot = _load_snapshot()

    kommune_subset: list[str] | None = config.get("kommune_subset")
    column_specs: dict[str, Any] = config.get("columns", _DEFAULT_COLUMN_SPECS)
    planted_fnr_count: int = int(config.get("planted_fnr_count", 0))

    commune_list, commune_weights, age_sex_weights, ages = _build_weight_arrays(
        snapshot, kommune_subset
    )

    ages_arr = np.array(ages, dtype=int)

    # Normalise commune weights
    cw = commune_weights.copy()
    cw_total = cw.sum()
    if cw_total <= 0:
        raise ValueError("All commune weights are zero — cannot sample.")
    cw_probs = cw / cw_total

    # Draw communes
    commune_indices = rng.choice(len(commune_list), size=n, p=cw_probs)
    komunner = [commune_list[i] for i in commune_indices]

    # Draw sex (1 or 2) — sex is determined first so we can draw age conditionally
    sex_arr = rng.integers(1, 3, size=n)  # uniform sex marginal; age then conditioned

    # Draw age conditional on kommune + sex
    ages_out = np.empty(n, dtype=int)
    for i in range(n):
        kom = komunner[i]
        sx = int(sex_arr[i])
        age_probs = age_sex_weights[kom][sx]
        ages_out[i] = ages_arr[int(rng.choice(len(ages_arr), p=age_probs))]

    # Build output dict
    out: dict[str, Any] = {
        "kommune": komunner,
        "age": ages_out.tolist(),
        "sex": sex_arr.tolist(),
    }

    # Apply CPT columns
    for col_name, spec in column_specs.items():
        if spec.get("type") != "cpt":
            raise ValueError(f"Only 'cpt' column type is supported; got {spec.get('type')!r} for {col_name!r}")
        cpt = spec["cpt"]
        categories = spec["categories"]
        col_values = []
        for age, sx in zip(ages_out, sex_arr):
            col_values.append(_apply_cpt(int(age), int(sx), cpt, categories, rng))
        out[col_name] = col_values

    # Notes column (optional)
    if planted_fnr_count > 0:
        out["notes"] = _generate_notes_column(n, rng, planted_fnr_count)

    df = pd.DataFrame(out)
    return df
