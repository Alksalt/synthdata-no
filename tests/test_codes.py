"""Tests for synthdata_no.codes — typed code registries."""
from __future__ import annotations

import json
import re

import pytest

from synthdata_no.codes import (
    ATCEntry,
    ICD10Entry,
    LOINCEntry,
    load_atc_fest,
    load_icd10_codes,
    load_loinc_min,
)


# ---------------------------------------------------------------------------
# ATC / FEST registry
# ---------------------------------------------------------------------------

def test_atc_fest_loads():
    entries = load_atc_fest()
    assert len(entries) >= 50, f"Expected ≥50 ATC entries, got {len(entries)}"


def test_atc_fest_schema():
    entries = load_atc_fest()
    for e in entries:
        assert isinstance(e, ATCEntry)
        assert re.match(r"^[A-Z]\d{2}[A-Z]{2}\d{2}$", e.atc), (
            f"ATC code malformed: {e.atc!r}"
        )
        assert e.varenavn, f"varenavn empty for {e.atc}"
        assert e.atc_name, f"atc_name empty for {e.atc}"


def test_atc_fest_attribution_present():
    import json
    from importlib.resources import files
    data = json.loads(files("synthdata_no.data").joinpath("atc_fest.json").read_text())
    attr = data.get("attribution", "")
    assert "DMP" in attr, "FEST attribution must mention DMP"
    assert "NLOD" in attr, "FEST attribution must mention NLOD"


# ---------------------------------------------------------------------------
# LOINC registry
# ---------------------------------------------------------------------------

def test_loinc_loads_and_count():
    entries = load_loinc_min()
    assert 4 <= len(entries) <= 10, f"Expected 4–10 LOINC entries, got {len(entries)}"


def test_loinc_schema():
    entries = load_loinc_min()
    for e in entries:
        assert isinstance(e, LOINCEntry)
        assert re.match(r"^\d+-\d+$", e.loinc), f"LOINC code malformed: {e.loinc!r}"
        assert e.component, f"component empty for {e.loinc}"
        assert e.unit, f"unit empty for {e.loinc}"


def test_loinc_contains_core_codes():
    """The four core LOINC codes from the plan must be present."""
    codes = {e.loinc for e in load_loinc_min()}
    assert "2160-0" in codes, "Creatinine (2160-0) missing"
    assert "718-7" in codes, "Hemoglobin (718-7) missing"
    assert "2345-7" in codes, "Glucose (2345-7) missing"
    assert "98980-6" in codes, "eGFR (98980-6) missing"


def test_loinc_attribution_present():
    from importlib.resources import files
    data = json.loads(files("synthdata_no.data").joinpath("loinc_min.json").read_text())
    attr = data.get("attribution", "")
    assert "Regenstrief" in attr, "Regenstrief attribution notice missing from loinc_min.json"
    assert "LOINC" in attr, "LOINC mention missing from attribution"


# ---------------------------------------------------------------------------
# ICD-10 registry — explicit test: NO Norwegian display text
# ---------------------------------------------------------------------------

def test_icd10_loads_and_count():
    entries = load_icd10_codes()
    assert len(entries) >= 50, f"Expected ≥50 ICD-10 entries, got {len(entries)}"


def test_icd10_schema():
    entries = load_icd10_codes()
    for e in entries:
        assert isinstance(e, ICD10Entry)
        assert re.match(r"^[A-Z]\d{2}(\.\d+)?$", e.code), (
            f"ICD-10 code malformed: {e.code!r}"
        )
        assert e.chapter, f"chapter empty for {e.code}"


def test_icd10_no_norwegian_display_text():
    """CRITICAL: committed icd10_codes.json must NOT embed any Norwegian display names.
    Each entry must have only 'code' and 'chapter' fields."""
    from importlib.resources import files
    data = json.loads(files("synthdata_no.data").joinpath("icd10_codes.json").read_text())
    for entry in data["codes"]:
        keys = set(entry.keys())
        assert keys == {"code", "chapter"}, (
            f"ICD-10 entry {entry.get('code')!r} has unexpected fields {keys - {'code','chapter'}}. "
            "Norwegian display names must NOT be embedded (uncleared WHO translation)."
        )


def test_icd10_no_display_or_name_field():
    """Extra assertion: no 'display', 'name', 'text', or 'description' field anywhere."""
    from importlib.resources import files
    raw = files("synthdata_no.data").joinpath("icd10_codes.json").read_text()
    forbidden_fields = ["display", "name", "text", "description", "navn", "tekst"]
    for field in forbidden_fields:
        assert f'"{field}"' not in raw, (
            f"Field {field!r} found in icd10_codes.json — Norwegian display text is forbidden."
        )


# ---------------------------------------------------------------------------
# User-supplied display file
# ---------------------------------------------------------------------------

def test_icd10_user_display_file(tmp_path):
    """User can provide a JSON mapping code→display; loader enriches entries."""
    display_file = tmp_path / "display.json"
    display_file.write_text(json.dumps({"I10": "Essensiell hypertensjon", "E11": "Diabetes mellitus type 2"}))
    entries = load_icd10_codes(display_file=display_file)
    by_code = {e.code: e for e in entries}
    assert by_code["I10"].display == "Essensiell hypertensjon"
    assert by_code["E11"].display == "Diabetes mellitus type 2"
    # Code without display file entry has display=None
    assert by_code.get("J18") is not None
    assert by_code["J18"].display is None


# ---------------------------------------------------------------------------
# N13 — load_icd10_codes wraps JSON errors with file path
# ---------------------------------------------------------------------------

def test_icd10_invalid_json_raises_value_error_with_path(tmp_path):
    """N13: malformed display_file JSON raises ValueError naming the file."""
    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{not valid json}", encoding="utf-8")
    with pytest.raises(ValueError, match=str(bad_json)):
        load_icd10_codes(display_file=bad_json)


def test_icd10_display_file_wrong_type_raises_value_error(tmp_path):
    """N13: display_file containing a JSON array (not dict) raises ValueError."""
    array_json = tmp_path / "array.json"
    array_json.write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(ValueError, match="must contain a JSON object"):
        load_icd10_codes(display_file=array_json)
