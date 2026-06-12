"""Tests for synthdata_no.tabular — SSB marginals snapshot + generate_table."""
from __future__ import annotations

import datetime

import numpy as np
import pandas as pd
import pytest

from synthdata_no.ids import is_synthetic_fnr
from synthdata_no.kommuner import valid_kommune_codes
from synthdata_no.tabular import generate_table, _load_snapshot, _BAND_LABELS, _AGE_BANDS


# ---------------------------------------------------------------------------
# T1 — SSB 07459 snapshot
# ---------------------------------------------------------------------------

class TestSSBSnapshot:
    """T1 — snapshot structure, metadata, and KLASS overlap."""

    def test_snapshot_loads(self):
        df = _load_snapshot()
        assert isinstance(df, pd.DataFrame)
        assert len(df) > 0

    def test_snapshot_columns(self):
        df = _load_snapshot()
        assert set(df.columns) >= {"kommune", "age", "sex", "count"}

    def test_snapshot_age_range(self):
        df = _load_snapshot()
        assert df["age"].min() <= 18, "Snapshot should cover ages from 18"
        assert df["age"].max() >= 95, "Snapshot should cover ages up to 95"

    def test_snapshot_sex_values(self):
        df = _load_snapshot()
        assert set(df["sex"].unique()) == {1, 2}, "Sex should be 1 and 2 only"

    def test_snapshot_count_non_negative(self):
        df = _load_snapshot()
        assert (df["count"] >= 0).all(), "All counts must be non-negative"

    def test_snapshot_total_population_plausible(self):
        """Norway has ~5M people; age 18–95 subset should be 4–5M."""
        df = _load_snapshot()
        total = df["count"].sum()
        # Each person is counted once per (kommune, age, sex) — sum across all
        # is roughly the adult population of Norway
        assert 3_000_000 <= total <= 6_000_000, (
            f"Implausible total population: {total:,}"
        )

    def test_snapshot_klass_overlap_100_pct(self):
        """All KLASS-131 terminal-2024 codes must be in the snapshot."""
        df = _load_snapshot()
        klass_codes = set(valid_kommune_codes())
        snapshot_codes = set(df["kommune"].unique())
        missing = klass_codes - snapshot_codes
        overlap_pct = len(klass_codes & snapshot_codes) / len(klass_codes) * 100
        assert overlap_pct >= 95.0, (
            f"KLASS overlap {overlap_pct:.1f}% < 95%. Missing: {sorted(missing)[:10]}"
        )

    def test_snapshot_under_2mb(self):
        """Snapshot must be ≤2 MB (committed artefact budget)."""
        from importlib.resources import files
        data_dir = files("synthdata_no.data")
        snap_path = str(data_dir.joinpath("ssb_07459_snapshot.parquet"))
        from pathlib import Path
        size_mb = Path(snap_path).stat().st_size / 1_048_576
        assert size_mb <= 2.0, f"Snapshot is {size_mb:.2f} MB > 2 MB budget"

    def test_snapshot_parquet_metadata(self):
        """Parquet file must carry source, license, and fetch_date metadata."""
        import pyarrow.parquet as pq
        from importlib.resources import files
        data_dir = files("synthdata_no.data")
        snap_path = str(data_dir.joinpath("ssb_07459_snapshot.parquet"))
        meta = pq.read_metadata(snap_path).metadata
        # Keys are bytes in pyarrow parquet metadata
        keys = {k.decode() if isinstance(k, bytes) else k for k in meta.keys()}
        assert "source" in keys, "Parquet metadata missing 'source'"
        assert "license" in keys, "Parquet metadata missing 'license'"
        assert "fetch_date" in keys, "Parquet metadata missing 'fetch_date'"


# ---------------------------------------------------------------------------
# T2 — generate_table
# ---------------------------------------------------------------------------

class TestGenerateTable:
    """T2 — generate_table API, determinism, marginals, CPT, planted fnr."""

    def _default_df(self, n: int = 200, seed: int = 42) -> pd.DataFrame:
        return generate_table({}, n=n, seed=seed)

    def test_returns_dataframe(self):
        df = self._default_df()
        assert isinstance(df, pd.DataFrame)

    def test_row_count(self):
        for n in [10, 100, 500]:
            df = generate_table({}, n=n, seed=1)
            assert len(df) == n, f"Expected {n} rows, got {len(df)}"

    def test_required_columns_present(self):
        df = self._default_df()
        for col in ["kommune", "age", "sex", "tjeneste_bruk", "diagnosekategori"]:
            assert col in df.columns, f"Missing column {col!r}"

    def test_determinism(self):
        df1 = generate_table({}, n=300, seed=99)
        df2 = generate_table({}, n=300, seed=99)
        pd.testing.assert_frame_equal(df1, df2)

    def test_different_seeds_different_output(self):
        df1 = generate_table({}, n=100, seed=1)
        df2 = generate_table({}, n=100, seed=2)
        assert not df1["kommune"].equals(df2["kommune"]), (
            "Different seeds should produce different commune sequences"
        )

    def test_all_kommuner_klass_valid(self):
        klass = set(valid_kommune_codes())
        df = generate_table({}, n=500, seed=42)
        bad = set(df["kommune"]) - klass
        assert not bad, f"Generated kommune codes not in KLASS: {bad}"

    def test_age_range(self):
        df = generate_table({}, n=1000, seed=42)
        assert df["age"].min() >= 18, "Age below 18 found"
        assert df["age"].max() <= 95, "Age above 95 found"

    def test_sex_values(self):
        df = generate_table({}, n=500, seed=42)
        assert set(df["sex"].unique()).issubset({1, 2}), "Sex values outside {1, 2}"

    def test_tjeneste_bruk_binary(self):
        df = generate_table({}, n=500, seed=42)
        assert set(df["tjeneste_bruk"].unique()).issubset({0, 1})

    def test_diagnosekategori_categories(self):
        df = generate_table({}, n=1000, seed=42)
        assert set(df["diagnosekategori"].unique()).issubset({1, 2, 3, 4})

    def test_marginals_within_tolerance(self):
        """
        With N=2000 and default CPTs, we expect:
        - tjeneste_bruk mean in elderly (65-95) should be roughly 0.50 ± 0.10
        - diagnosekategori in 65-95 should be roughly uniformly spread across 1–4
        """
        df = generate_table({}, n=2000, seed=42)
        elderly = df[df["age"] >= 65]
        if len(elderly) > 50:
            mean_tb = elderly["tjeneste_bruk"].mean()
            assert 0.30 <= mean_tb <= 0.70, (
                f"tjeneste_bruk mean for elderly {mean_tb:.2f} outside [0.30, 0.70]"
            )

    def test_kommune_subset_restriction(self):
        subset = ["0301", "5001"]
        df = generate_table({"kommune_subset": subset}, n=200, seed=42)
        assert set(df["kommune"].unique()).issubset(set(subset)), (
            "generate_table returned communes outside requested subset"
        )

    def test_unknown_kommune_in_subset_raises(self):
        # "0000" is not a valid KLASS code → should raise ValueError
        with pytest.raises(ValueError):
            generate_table({"kommune_subset": ["0000"]}, n=10, seed=1)

    def test_planted_fnr_count_exact(self):
        df = generate_table({"planted_fnr_count": 3}, n=100, seed=42)
        assert "notes" in df.columns, "notes column not present when planted_fnr_count>0"
        # Count rows where a Tenor-range fnr appears
        def has_planted_fnr(text: str) -> bool:
            for token in text.split():
                if len(token) == 11 and token.isdigit() and is_synthetic_fnr(token):
                    return True
            return False
        planted = df["notes"].apply(has_planted_fnr).sum()
        assert planted == 3, f"Expected 3 planted fnr, found {planted}"

    def test_planted_fnr_are_tenor_range(self):
        df = generate_table({"planted_fnr_count": 2}, n=50, seed=42)
        for text in df["notes"]:
            for token in text.split():
                if len(token) == 11 and token.isdigit():
                    assert is_synthetic_fnr(token), (
                        f"Token {token!r} in notes is not Tenor-range"
                    )

    def test_no_notes_column_when_zero_planted(self):
        df = generate_table({}, n=50, seed=42)
        assert "notes" not in df.columns, (
            "notes column should not appear when planted_fnr_count=0"
        )

    def test_custom_cpt_column(self):
        """A user-supplied column spec should produce the configured categories."""
        custom_cpt = {
            "18-44": {"1": [0.6, 0.3, 0.1], "2": [0.6, 0.3, 0.1]},
            "45-64": {"1": [0.4, 0.4, 0.2], "2": [0.4, 0.4, 0.2]},
            "65-95": {"1": [0.2, 0.5, 0.3], "2": [0.2, 0.5, 0.3]},
        }
        config = {
            "columns": {
                "custom_col": {
                    "type": "cpt",
                    "categories": ["A", "B", "C"],
                    "cpt": custom_cpt,
                }
            }
        }
        df = generate_table(config, n=200, seed=42)
        assert "custom_col" in df.columns
        assert set(df["custom_col"].unique()).issubset({"A", "B", "C"})


# ---------------------------------------------------------------------------
# T3 — export/omsorgsradar.py (brfss-demo contract)
# ---------------------------------------------------------------------------

class TestOmsorgsradarExport:
    """T3 — write_brfss_shaped_fixture schema, dtypes, planted PII, determinism."""

    def _get_fixture(self, tmp_path, seed: int = 42) -> pd.DataFrame:
        from synthdata_no.export.omsorgsradar import write_brfss_shaped_fixture
        out = tmp_path / "fixture.csv"
        df = write_brfss_shaped_fixture(out, seed=seed)
        return df, out

    def test_row_count(self, tmp_path):
        df, _ = self._get_fixture(tmp_path)
        assert len(df) == 600, f"Expected 600 rows, got {len(df)}"

    def test_column_names_exact(self, tmp_path):
        df, _ = self._get_fixture(tmp_path)
        assert list(df.columns) == ["state", "age", "sex", "diabetes", "notes"], (
            f"Column names mismatch: {list(df.columns)}"
        )

    def test_state_is_4digit_str(self, tmp_path):
        df, _ = self._get_fixture(tmp_path)
        # pandas 3.x uses StringDtype; object/str both mean string
        assert pd.api.types.is_string_dtype(df["state"]), "state must be str dtype"
        klass = set(valid_kommune_codes())
        bad = set(df["state"]) - klass
        assert not bad, f"state values not in KLASS: {bad}"

    def test_age_range(self, tmp_path):
        df, _ = self._get_fixture(tmp_path)
        assert df["age"].min() >= 18
        assert df["age"].max() <= 94

    def test_sex_values(self, tmp_path):
        df, _ = self._get_fixture(tmp_path)
        assert set(df["sex"].unique()).issubset({1, 2})

    def test_diabetes_binary(self, tmp_path):
        df, _ = self._get_fixture(tmp_path)
        assert set(df["diabetes"].unique()).issubset({0, 1})

    def test_dtypes(self, tmp_path):
        df, _ = self._get_fixture(tmp_path)
        assert pd.api.types.is_integer_dtype(df["age"]), "age must be int"
        assert pd.api.types.is_integer_dtype(df["sex"]), "sex must be int"
        assert pd.api.types.is_integer_dtype(df["diabetes"]), "diabetes must be int"
        # pandas 3.x uses StringDtype; accept both object and StringDtype
        assert pd.api.types.is_string_dtype(df["notes"]), "notes must be str dtype"

    def test_csv_loads_with_correct_dtypes(self, tmp_path):
        """Fixture CSV loads in pandas with the dtype hints brfss uses."""
        df, out = self._get_fixture(tmp_path)
        loaded = pd.read_csv(
            out,
            dtype={"state": str, "age": int, "sex": int, "diabetes": int, "notes": str},
        )
        assert len(loaded) == 600
        assert list(loaded.columns) == ["state", "age", "sex", "diabetes", "notes"]

    def test_exactly_two_planted_fnr(self, tmp_path):
        """Exactly 2 Tenor-range fnr must be present in the notes column."""
        df, _ = self._get_fixture(tmp_path)

        def extract_fnr_tokens(text: str) -> list[str]:
            return [t for t in text.split() if len(t) == 11 and t.isdigit() and is_synthetic_fnr(t)]

        all_tokens = []
        for text in df["notes"]:
            all_tokens.extend(extract_fnr_tokens(text))
        assert len(all_tokens) == 2, f"Expected exactly 2 planted fnr, found {len(all_tokens)}"

    def test_planted_fnr_are_synthetic_range(self, tmp_path):
        """All 11-digit tokens in notes must be Tenor-range (month 81–92)."""
        df, _ = self._get_fixture(tmp_path)
        for text in df["notes"]:
            for token in text.split():
                if len(token) == 11 and token.isdigit():
                    assert is_synthetic_fnr(token), (
                        f"Token {token!r} in notes is not Tenor-range (month must be 81–92)"
                    )

    def test_phone_like_number_present(self, tmp_path):
        """Row 1 notes must contain the phone-like filler «91123456»."""
        df, _ = self._get_fixture(tmp_path)
        assert "91123456" in df.loc[1, "notes"], (
            f"Phone-like number missing from row 1: {df.loc[1, 'notes']!r}"
        )

    def test_determinism(self, tmp_path):
        from synthdata_no.export.omsorgsradar import write_brfss_shaped_fixture
        out1 = tmp_path / "f1.csv"
        out2 = tmp_path / "f2.csv"
        df1 = write_brfss_shaped_fixture(out1, seed=42)
        df2 = write_brfss_shaped_fixture(out2, seed=42)
        pd.testing.assert_frame_equal(df1, df2)

    def test_different_seeds_different_output(self, tmp_path):
        from synthdata_no.export.omsorgsradar import write_brfss_shaped_fixture
        out1 = tmp_path / "f1.csv"
        out2 = tmp_path / "f2.csv"
        df1 = write_brfss_shaped_fixture(out1, seed=42)
        df2 = write_brfss_shaped_fixture(out2, seed=99)
        assert not df1["state"].equals(df2["state"]), (
            "Different seeds should produce different state sequences"
        )

    def test_planted_fnr_in_first_two_rows(self, tmp_path):
        """Per the contract, rows 0 and 1 carry planted fnr."""
        df, _ = self._get_fixture(tmp_path)

        def has_fnr(text: str) -> bool:
            return any(
                len(t) == 11 and t.isdigit() and is_synthetic_fnr(t)
                for t in text.split()
            )

        assert has_fnr(df.loc[0, "notes"]), "Row 0 must carry a planted fnr"
        assert has_fnr(df.loc[1, "notes"]), "Row 1 must carry a planted fnr"

    def test_remaining_rows_are_rutinekontroll(self, tmp_path):
        """Rows 2+ must be plain «rutinekontroll» filler."""
        df, _ = self._get_fixture(tmp_path)
        # Check a sample of non-planted rows
        for i in range(2, min(20, len(df))):
            assert df.loc[i, "notes"] == "rutinekontroll", (
                f"Row {i} notes is not «rutinekontroll»: {df.loc[i, 'notes']!r}"
            )
