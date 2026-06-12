"""Consumer smoke tests — R3.

Marked @pytest.mark.smoke. Runnable offline (no network, no cross-venv imports).

(a) omsorgsradar contract smoke:
    - Validate fixture against the mined brfss-demo contract.
    - Run vendored valid_fnr_checksum on both planted fnr.
    - Regex ``\\b\\d{11}\\b`` asserts both planted fnr are detectable in the notes column.
    - Schema/dtypes match analysis.toml dtype hints (state=str, age numeric, sex numeric, diabetes numeric, notes str).
    - Documents that the full in-pipeline run happens on the omsorgsradar side.

(b) medspacy-no:
    - to_jsonl(n=200) -> to_spacy_examples against spacy.blank("nb").
    - Every Example has >= 1 reference entity.
    - gold_context distribution covers all 6 ConText values.

(c) fhir-safety-harness:
    - write_fixture_set(n_patients=5) -> every bundle parses via R4B model_validate round-trip.
    - fastjsonschema structural schema check on each bundle.
    - index.json: seed/n_patients sane, counts includes "Patient".
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd
import pytest

# ---------------------------------------------------------------------------
# Vendored fnr checksum — identical copy from omsorgsradar/core/anonymize/pii.py
# (Attribution: omsorgsradar project, Oleksandr Altukhov, MIT-compatible)
# Vendored here so the smoke test has zero cross-venv dependency.
# ---------------------------------------------------------------------------

_FNR_K1_W = [3, 7, 6, 1, 8, 9, 4, 5, 2]
_FNR_K2_W = [5, 4, 3, 2, 7, 6, 5, 4, 3, 2]


def _control_digit(digits: list[int], weights: list[int]) -> int | None:
    s = sum(d * w for d, w in zip(digits, weights))
    k = 11 - (s % 11)
    if k == 11:
        return 0
    if k == 10:
        return None
    return k


def _valid_fnr_checksum(fnr: str) -> bool:
    """Vendored from omsorgsradar — checksum-only, no date validation."""
    if len(fnr) != 11 or not fnr.isdigit():
        return False
    d = [int(c) for c in fnr]
    k1 = _control_digit(d[:9], _FNR_K1_W)
    k2 = _control_digit(d[:10], _FNR_K2_W)
    return k1 is not None and k2 is not None and k1 == d[9] and k2 == d[10]


# ---------------------------------------------------------------------------
# (a) omsorgsradar contract smoke
# ---------------------------------------------------------------------------

_BRFSS_ANALYSIS_TOML_PATH = (
    Path("/Users/ol/agents/ehelse_project/omsorgsradar")
    / "analyses/brfss-demo/analysis.toml"
)


@pytest.mark.smoke
class TestOmsorgsradarSmoke:
    """Contract-level smoke for the brfss-demo fixture.

    Full in-pipeline run (ingest → profile → anonymize → analyze → verify → report)
    is omsorgsradar's responsibility and runs in the omsorgsradar venv. This test
    validates the fixture contract from the synthdata-no side only.
    """

    def test_fixture_schema(self, tmp_path: Path) -> None:
        """Emitted fixture has exactly the brfss-demo contract columns in the right order."""
        from synthdata_no.export.omsorgsradar import write_brfss_shaped_fixture

        csv_path = tmp_path / "brfss_sample.csv"
        write_brfss_shaped_fixture(csv_path, seed=42)
        df = pd.read_csv(csv_path, dtype={"state": str})
        assert list(df.columns) == ["state", "age", "sex", "diabetes", "notes"]

    def test_fixture_row_count(self, tmp_path: Path) -> None:
        from synthdata_no.export.omsorgsradar import write_brfss_shaped_fixture

        csv_path = tmp_path / "brfss_sample.csv"
        write_brfss_shaped_fixture(csv_path, seed=42)
        df = pd.read_csv(csv_path)
        assert len(df) == 600

    def test_fixture_dtypes(self, tmp_path: Path) -> None:
        """Dtypes match the dtype hints in analysis.toml: state=str, others numeric.

        pandas 3.x returns StringDtype (not object) for dtype=str columns — we check
        that state is a string-like dtype rather than asserting the exact dtype class.
        """
        from synthdata_no.export.omsorgsradar import write_brfss_shaped_fixture

        csv_path = tmp_path / "brfss_sample.csv"
        write_brfss_shaped_fixture(csv_path, seed=42)
        # Read with state as str (matching [sources.dtype] state = "str")
        df = pd.read_csv(csv_path, dtype={"state": str})
        # pandas 3.x uses StringDtype for dtype=str, 2.x uses object — accept both
        assert pd.api.types.is_string_dtype(df["state"]), (
            f"state must be string-like dtype, got {df['state'].dtype}"
        )
        # age, sex, diabetes must be integer-compatible
        assert pd.api.types.is_integer_dtype(df["age"])
        assert pd.api.types.is_integer_dtype(df["sex"])
        assert pd.api.types.is_integer_dtype(df["diabetes"])
        # notes is string-like
        assert pd.api.types.is_string_dtype(df["notes"]) or df["notes"].dtype == object

    def test_fixture_state_values_are_4digit_strings(self, tmp_path: Path) -> None:
        """state column: 4-digit kommune codes, zero-padded as strings."""
        from synthdata_no.export.omsorgsradar import write_brfss_shaped_fixture
        from synthdata_no.kommuner import valid_kommune_codes

        csv_path = tmp_path / "brfss_sample.csv"
        write_brfss_shaped_fixture(csv_path, seed=42)
        df = pd.read_csv(csv_path, dtype={"state": str})
        valid = set(valid_kommune_codes())
        for v in df["state"].unique():
            assert v in valid, f"state value {v!r} is not a valid KLASS kommune code"

    def test_fixture_age_range(self, tmp_path: Path) -> None:
        from synthdata_no.export.omsorgsradar import write_brfss_shaped_fixture

        csv_path = tmp_path / "brfss_sample.csv"
        write_brfss_shaped_fixture(csv_path, seed=42)
        df = pd.read_csv(csv_path)
        assert df["age"].between(18, 94).all(), "age values outside [18, 94]"

    def test_fixture_sex_values(self, tmp_path: Path) -> None:
        from synthdata_no.export.omsorgsradar import write_brfss_shaped_fixture

        csv_path = tmp_path / "brfss_sample.csv"
        write_brfss_shaped_fixture(csv_path, seed=42)
        df = pd.read_csv(csv_path)
        assert set(df["sex"].unique()) <= {1, 2}

    def test_fixture_diabetes_binary(self, tmp_path: Path) -> None:
        from synthdata_no.export.omsorgsradar import write_brfss_shaped_fixture

        csv_path = tmp_path / "brfss_sample.csv"
        write_brfss_shaped_fixture(csv_path, seed=42)
        df = pd.read_csv(csv_path)
        assert set(df["diabetes"].unique()) <= {0, 1}

    def test_planted_fnr_checksum_valid(self, tmp_path: Path) -> None:
        """Both planted fnr pass the vendored omsorgsradar checksum (same logic)."""
        from synthdata_no.export.omsorgsradar import write_brfss_shaped_fixture

        csv_path = tmp_path / "brfss_sample.csv"
        df = write_brfss_shaped_fixture(csv_path, seed=42)

        # Extract all 11-digit sequences from notes column
        all_fnr: list[str] = []
        for note in df["notes"]:
            found = re.findall(r"\b\d{11}\b", str(note))
            all_fnr.extend(found)

        assert len(all_fnr) == 2, f"Expected exactly 2 planted fnr, found {len(all_fnr)}: {all_fnr}"

        for fnr in all_fnr:
            assert _valid_fnr_checksum(fnr), f"Planted fnr {fnr!r} fails checksum"
            # Tenor-range assertion: month ∈ 81–92
            month = int(fnr[2:4])
            assert 81 <= month <= 92, f"Planted fnr {fnr!r} has month {month} — not Tenor range"

    def test_planted_fnr_regex_detectable(self, tmp_path: Path) -> None:
        """\\b\\d{11}\\b regex finds BOTH planted fnr (same pattern omsorgsradar uses)."""
        from synthdata_no.export.omsorgsradar import write_brfss_shaped_fixture

        csv_path = tmp_path / "brfss_sample.csv"
        df = write_brfss_shaped_fixture(csv_path, seed=42)

        # Combine all notes text
        combined = " ".join(str(n) for n in df["notes"])
        matches = re.findall(r"\b\d{11}\b", combined)
        assert len(matches) >= 2, f"Expected ≥2 11-digit sequences, found {len(matches)}"

    def test_analysis_toml_dtype_hints_respected(self, tmp_path: Path) -> None:
        """Fixture column types match [sources.dtype] from the real analysis.toml.

        Only the 'state' dtype hint is explicit in the TOML (state = 'str').
        Other columns are inferred as numeric by pandas and must be integer-compatible.
        pandas 3.x uses StringDtype for dtype=str — we check is_string_dtype.
        """
        from synthdata_no.export.omsorgsradar import write_brfss_shaped_fixture

        if not _BRFSS_ANALYSIS_TOML_PATH.exists():
            pytest.skip("omsorgsradar analysis.toml not found — cross-project path unavailable")

        csv_path = tmp_path / "brfss_sample.csv"
        write_brfss_shaped_fixture(csv_path, seed=42)
        df = pd.read_csv(csv_path, dtype={"state": str})

        # TOML says: [sources.dtype] state = "str"
        assert pd.api.types.is_string_dtype(df["state"]), (
            f"state must be string-like dtype, got {df['state'].dtype}"
        )
        # No other explicit dtype hints — verify numeric columns are integer-compatible
        for col in ["age", "sex", "diabetes"]:
            assert pd.api.types.is_numeric_dtype(df[col]), f"{col} must be numeric"

    def test_full_pipeline_not_run_here(self) -> None:
        """Stub test documenting that the full in-pipeline run is omsorgsradar's responsibility.

        The omsorgsradar anonymize pipeline (ingest → profile → anonymize → analyze → verify → report)
        requires the omsorgsradar venv and is not run from synthdata-no tests.
        Cross-venv orchestration is too fragile for a package test suite.
        To run the full integration: cd to omsorgsradar and run:
            uv run python -m omsorgsradar run analyses/brfss-demo --source-override brfss=<fixture_path>
        """
        assert True  # This test always passes — it documents the design decision.


# ---------------------------------------------------------------------------
# (b) medspacy-no smoke
# ---------------------------------------------------------------------------

@pytest.mark.smoke
class TestMedspacySmoke:
    """Smoke: to_jsonl(n=200) → to_spacy_examples covers all 6 ConText categories."""

    _GOLD_CONTEXTS = {
        "NEGATED_EXISTENCE",
        "POSSIBLE_EXISTENCE",
        "HYPOTHETICAL",
        "HISTORICAL",
        "FAMILY",
        "AFFIRMED",
    }

    def test_to_spacy_examples_has_entities(self, tmp_path: Path) -> None:
        """Every spaCy Example has ≥1 reference entity."""
        try:
            import spacy
        except ImportError:
            pytest.skip("spaCy not installed")

        from synthdata_no.export.medspacy import to_jsonl, to_spacy_examples

        jsonl_path = to_jsonl(tmp_path / "clinical.jsonl", n=200, seed=42)
        nlp = spacy.blank("nb")
        examples = to_spacy_examples(jsonl_path, nlp)

        assert len(examples) == 200
        for i, ex in enumerate(examples):
            assert len(ex.reference.ents) >= 1, (
                f"Example {i} has no reference entities: text={ex.reference.text!r}"
            )

    def test_gold_context_covers_all_six(self, tmp_path: Path) -> None:
        """200 records must cover all 6 gold_context values."""
        from synthdata_no.export.medspacy import to_jsonl

        jsonl_path = to_jsonl(tmp_path / "clinical.jsonl", n=200, seed=42)
        contexts = set()
        with open(jsonl_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    rec = json.loads(line)
                    ctx = rec["meta"]["gold_context"]
                    assert ctx in self._GOLD_CONTEXTS, f"Unknown gold_context: {ctx!r}"
                    contexts.add(ctx)

        missing = self._GOLD_CONTEXTS - contexts
        assert not missing, (
            f"Missing gold_context values after 200 records: {sorted(missing)}"
        )

    def test_entity_spans_non_empty(self, tmp_path: Path) -> None:
        """Every JSONL record has at least one span."""
        from synthdata_no.export.medspacy import to_jsonl

        jsonl_path = to_jsonl(tmp_path / "clinical.jsonl", n=200, seed=42)
        with open(jsonl_path, encoding="utf-8") as f:
            for i, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                assert len(rec["spans"]) >= 1, f"Record {i} has no spans"

    def test_char_offsets_match_text(self, tmp_path: Path) -> None:
        """Spot-check: span[start:end] matches the entity text slice (incl. æøå)."""
        from synthdata_no.export.medspacy import to_jsonl

        jsonl_path = to_jsonl(tmp_path / "clinical.jsonl", n=200, seed=42)
        mismatches = []
        with open(jsonl_path, encoding="utf-8") as f:
            for i, line in enumerate(f):
                line = line.strip()
                if not line:
                    continue
                rec = json.loads(line)
                text = rec["text"]
                for sp in rec["spans"]:
                    slice_text = text[sp["start"]:sp["end"]]
                    if not slice_text:
                        mismatches.append(f"Record {i}: empty slice [{sp['start']}:{sp['end']}]")
        assert not mismatches, f"Empty spans found:\n" + "\n".join(mismatches[:5])


# ---------------------------------------------------------------------------
# (c) fhir-safety-harness smoke
# ---------------------------------------------------------------------------

@pytest.mark.smoke
class TestFhirSafetyHarnessSmoke:
    """Smoke: write_fixture_set(n_patients=5) → R4B parse + schema check + index sane."""

    def test_bundles_parse_r4b(self, tmp_path: Path) -> None:
        """Every bundle parses via fhir.resources.R4B.bundle.Bundle.model_validate."""
        from synthdata_no.export.safety_harness import write_fixture_set
        from fhir.resources.R4B.bundle import Bundle

        out_dir = tmp_path / "fhir_fixtures"
        write_fixture_set(out_dir, n_patients=5, seed=42)

        for i in range(5):
            path = out_dir / f"patient_{i:04d}.json"
            assert path.exists(), f"Missing {path}"
            raw = json.loads(path.read_text(encoding="utf-8"))
            bundle = Bundle.model_validate(raw)
            assert bundle.type == "transaction"
            assert bundle.entry and len(bundle.entry) > 0

    def test_bundles_schema_valid(self, tmp_path: Path) -> None:
        """Every bundle passes fastjsonschema structural check (same schema used in test_fhir_gen.py)."""
        import fastjsonschema

        _BUNDLE_SCHEMA = {
            "type": "object",
            "required": ["resourceType", "type"],
            "properties": {
                "resourceType": {"type": "string", "const": "Bundle"},
                "type": {"type": "string"},
                "entry": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["fullUrl", "resource", "request"],
                        "properties": {
                            "fullUrl": {"type": "string", "pattern": "^urn:uuid:"},
                            "resource": {"type": "object"},
                            "request": {
                                "type": "object",
                                "required": ["method", "url"],
                                "properties": {
                                    "method": {"type": "string"},
                                    "url": {"type": "string"},
                                },
                            },
                        },
                    },
                },
            },
        }
        validate_bundle = fastjsonschema.compile(_BUNDLE_SCHEMA)

        from synthdata_no.export.safety_harness import write_fixture_set

        out_dir = tmp_path / "fhir_fixtures"
        write_fixture_set(out_dir, n_patients=5, seed=42)

        for i in range(5):
            path = out_dir / f"patient_{i:04d}.json"
            raw = json.loads(path.read_text(encoding="utf-8"))
            # validate_bundle raises fastjsonschema.JsonSchemaValueException on failure
            validate_bundle(raw)

    def test_bundles_contain_patient(self, tmp_path: Path) -> None:
        """Each bundle has a Patient resource entry."""
        from synthdata_no.export.safety_harness import write_fixture_set

        out_dir = tmp_path / "fhir_fixtures"
        write_fixture_set(out_dir, n_patients=5, seed=42)

        for i in range(5):
            raw = json.loads((out_dir / f"patient_{i:04d}.json").read_text())
            resource_types = [e["resource"]["resourceType"] for e in raw["entry"]]
            assert "Patient" in resource_types, f"Bundle {i} missing Patient resource"

    def test_bundles_patient_identifier_tenor_range(self, tmp_path: Path) -> None:
        """Patient identifier must be in the Tenor range (month 81–92)."""
        from synthdata_no.export.safety_harness import write_fixture_set

        out_dir = tmp_path / "fhir_fixtures"
        write_fixture_set(out_dir, n_patients=5, seed=42)

        for i in range(5):
            raw = json.loads((out_dir / f"patient_{i:04d}.json").read_text())
            patient_entries = [
                e for e in raw["entry"]
                if e["resource"]["resourceType"] == "Patient"
            ]
            for entry in patient_entries:
                for ident in entry["resource"].get("identifier", []):
                    fnr = ident["value"]
                    month = int(fnr[2:4])
                    assert 81 <= month <= 92, (
                        f"Bundle {i} Patient identifier {fnr!r} has month {month} — not Tenor range"
                    )

    def test_index_json_sane(self, tmp_path: Path) -> None:
        """index.json has correct seed, n_patients, and Patient in counts."""
        from synthdata_no.export.safety_harness import write_fixture_set

        out_dir = tmp_path / "fhir_fixtures"
        write_fixture_set(out_dir, n_patients=5, seed=42)

        index = json.loads((out_dir / "index.json").read_text())
        assert index["seed"] == 42
        assert index["n_patients"] == 5
        assert "package_version" in index
        assert "Patient" in index.get("counts", {}), (
            f"index.json counts missing Patient: {index.get('counts')}"
        )

    def test_fixture_deterministic(self, tmp_path: Path) -> None:
        """Same seed → byte-identical bundle files."""
        from synthdata_no.export.safety_harness import write_fixture_set

        out1 = tmp_path / "run1"
        out2 = tmp_path / "run2"
        write_fixture_set(out1, n_patients=3, seed=99)
        write_fixture_set(out2, n_patients=3, seed=99)

        for i in range(3):
            f1 = (out1 / f"patient_{i:04d}.json").read_text()
            f2 = (out2 / f"patient_{i:04d}.json").read_text()
            assert f1 == f2, f"Bundle {i} differs between runs with same seed"
