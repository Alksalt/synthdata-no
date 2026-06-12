"""Tests for synthdata_no.export.safety_harness — H3 fixture scaffold.

Covers:
  - Bundle parse round-trip
  - Identifiers are synthetic-range (is_synthetic_fnr)
  - Medications carry BOTH FEST + ATC codings
  - References resolve within bundle (urn:uuid: refs found in entry fullUrls)
  - Byte-determinism across two write_fixture_set calls
"""
from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import numpy as np
import pytest

from fhir.resources.R4B.bundle import Bundle
from synthdata_no.codes import load_atc_fest, load_icd10_codes, load_loinc_min
from synthdata_no.export.safety_harness import patient_bundle, write_fixture_set
from synthdata_no.fhir_gen import _URI_ATC, _URI_FEST
from synthdata_no.ids import is_synthetic_fnr
from synthdata_no.persons import generate_person


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _bundle_dict(person, **kwargs) -> dict:
    rng = kwargs.pop("rng", np.random.default_rng(42))
    bundle = patient_bundle(person, rng=rng, **kwargs)
    return json.loads(bundle.model_dump_json())


def _get_resources_by_type(bundle_dict: dict, rtype: str) -> list[dict]:
    return [
        e["resource"]
        for e in bundle_dict.get("entry", [])
        if e.get("resource", {}).get("resourceType") == rtype
    ]


def _all_full_urls(bundle_dict: dict) -> set[str]:
    return {e["fullUrl"] for e in bundle_dict.get("entry", [])}


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def person():
    return generate_person(seed=42)


@pytest.fixture
def atc_entries():
    return load_atc_fest()[:2]


@pytest.fixture
def icd10_entries():
    return load_icd10_codes()[:2]


@pytest.fixture
def loinc_entries():
    entries = load_loinc_min()
    creatinine = next(e for e in entries if e.loinc == "2160-0")
    return [(creatinine, creatinine.default_value, creatinine.unit)]


# ---------------------------------------------------------------------------
# H3 — patient_bundle
# ---------------------------------------------------------------------------

class TestPatientBundle:
    def test_bundle_parse_round_trip(self, person, atc_entries, icd10_entries, loinc_entries):
        """R4B Bundle model_validate round-trip."""
        bundle = patient_bundle(
            person,
            meds=atc_entries,
            conditions=icd10_entries,
            observations=loinc_entries,
            rng=np.random.default_rng(42),
        )
        bundle_dict = json.loads(bundle.model_dump_json())
        Bundle.model_validate(bundle_dict)

    def test_patient_identifier_is_synthetic(self, person):
        """Patient identifier must be in the Tenor synthetic range."""
        bd = _bundle_dict(person, rng=np.random.default_rng(42))
        patients = _get_resources_by_type(bd, "Patient")
        assert len(patients) == 1
        patient = patients[0]
        identifiers = patient.get("identifier", [])
        assert len(identifiers) > 0
        fnr_value = identifiers[0]["value"]
        assert is_synthetic_fnr(fnr_value), (
            f"Patient identifier {fnr_value!r} is not in the synthetic Tenor range"
        )

    def test_medications_carry_fest_and_atc(self, person, atc_entries):
        """Every Medication resource must have both FEST and ATC codings."""
        bd = _bundle_dict(person, meds=atc_entries, rng=np.random.default_rng(42))
        meds = _get_resources_by_type(bd, "Medication")
        assert len(meds) == len(atc_entries)
        for med in meds:
            systems = {c["system"] for c in med["code"]["coding"]}
            assert _URI_FEST in systems, f"FEST coding missing in {med}"
            assert _URI_ATC in systems, f"ATC coding missing in {med}"

    def test_references_resolve_within_bundle(self, person, atc_entries, icd10_entries, loinc_entries):
        """Every urn:uuid: reference in subject/medicationReference points to a known fullUrl."""
        bd = _bundle_dict(
            person,
            meds=atc_entries,
            conditions=icd10_entries,
            observations=loinc_entries,
            rng=np.random.default_rng(42),
        )
        full_urls = _all_full_urls(bd)

        for entry in bd.get("entry", []):
            resource = entry.get("resource", {})
            # Check subject references
            if "subject" in resource:
                ref = resource["subject"].get("reference", "")
                if ref.startswith("urn:uuid:"):
                    assert ref in full_urls, (
                        f"subject reference {ref!r} not found in bundle fullUrls"
                    )
            # Check medicationReference
            if "medicationReference" in resource:
                ref = resource["medicationReference"].get("reference", "")
                if ref.startswith("urn:uuid:"):
                    assert ref in full_urls, (
                        f"medicationReference {ref!r} not found in bundle fullUrls"
                    )

    def test_no_meds_no_medication_resources(self, person):
        bd = _bundle_dict(person, rng=np.random.default_rng(42))
        meds = _get_resources_by_type(bd, "Medication")
        assert meds == []

    def test_bundle_type_transaction(self, person):
        bd = _bundle_dict(person, rng=np.random.default_rng(42))
        assert bd["type"] == "transaction"

    def test_all_entries_have_full_url(self, person, atc_entries, icd10_entries, loinc_entries):
        bd = _bundle_dict(
            person,
            meds=atc_entries,
            conditions=icd10_entries,
            observations=loinc_entries,
            rng=np.random.default_rng(42),
        )
        for entry in bd["entry"]:
            assert entry.get("fullUrl", "").startswith("urn:uuid:"), (
                f"Entry missing urn:uuid fullUrl: {entry.get('fullUrl')}"
            )

    def test_determinism_same_rng(self, person, atc_entries, icd10_entries, loinc_entries):
        """Same seed → identical serialized bundles."""
        b1 = patient_bundle(
            person,
            meds=atc_entries,
            conditions=icd10_entries,
            observations=loinc_entries,
            rng=np.random.default_rng(77),
        )
        b2 = patient_bundle(
            person,
            meds=atc_entries,
            conditions=icd10_entries,
            observations=loinc_entries,
            rng=np.random.default_rng(77),
        )
        assert b1.model_dump_json() == b2.model_dump_json()


# ---------------------------------------------------------------------------
# H3 — write_fixture_set
# ---------------------------------------------------------------------------

class TestWriteFixtureSet:
    def test_output_files_created(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            write_fixture_set(Path(tmpdir), n_patients=3, seed=42)
            files = list(Path(tmpdir).iterdir())
            json_files = [f for f in files if f.suffix == ".json"]
            assert len(json_files) == 4  # 3 patients + index.json

    def test_index_json_structure(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            write_fixture_set(Path(tmpdir), n_patients=2, seed=42)
            index = json.loads((Path(tmpdir) / "index.json").read_text())
            assert index["seed"] == 42
            assert index["n_patients"] == 2
            assert "package_version" in index
            assert "counts" in index
            assert isinstance(index["counts"], dict)

    def test_each_patient_file_parses_as_bundle(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            write_fixture_set(Path(tmpdir), n_patients=3, seed=42)
            for i in range(3):
                path = Path(tmpdir) / f"patient_{i:04d}.json"
                assert path.exists(), f"Missing {path.name}"
                bd = json.loads(path.read_text())
                Bundle.model_validate(bd)

    def test_patient_identifiers_synthetic_range(self):
        """All patient fnr values in the fixture set are Tenor-range."""
        with tempfile.TemporaryDirectory() as tmpdir:
            write_fixture_set(Path(tmpdir), n_patients=5, seed=42)
            for i in range(5):
                path = Path(tmpdir) / f"patient_{i:04d}.json"
                bd = json.loads(path.read_text())
                patients = [
                    e["resource"]
                    for e in bd.get("entry", [])
                    if e.get("resource", {}).get("resourceType") == "Patient"
                ]
                for patient in patients:
                    fnr = patient["identifier"][0]["value"]
                    assert is_synthetic_fnr(fnr), (
                        f"Non-synthetic fnr {fnr!r} in patient_{i:04d}.json"
                    )

    def test_medications_both_codings_in_fixture(self):
        """Fixture meds carry both FEST and ATC codings."""
        with tempfile.TemporaryDirectory() as tmpdir:
            write_fixture_set(Path(tmpdir), n_patients=2, seed=42)
            path = Path(tmpdir) / "patient_0000.json"
            bd = json.loads(path.read_text())
            meds = [
                e["resource"]
                for e in bd.get("entry", [])
                if e.get("resource", {}).get("resourceType") == "Medication"
            ]
            assert len(meds) > 0, "Expected at least one Medication in fixture"
            for med in meds:
                systems = {c["system"] for c in med["code"]["coding"]}
                assert _URI_FEST in systems
                assert _URI_ATC in systems

    def test_byte_determinism_across_two_runs(self):
        """Two calls with same seed → byte-identical files."""
        with tempfile.TemporaryDirectory() as dir1, tempfile.TemporaryDirectory() as dir2:
            write_fixture_set(Path(dir1), n_patients=3, seed=99)
            write_fixture_set(Path(dir2), n_patients=3, seed=99)

            for i in range(3):
                fname = f"patient_{i:04d}.json"
                content1 = (Path(dir1) / fname).read_text()
                content2 = (Path(dir2) / fname).read_text()
                assert content1 == content2, (
                    f"Byte mismatch in {fname} between two deterministic runs"
                )

            idx1 = (Path(dir1) / "index.json").read_text()
            idx2 = (Path(dir2) / "index.json").read_text()
            assert idx1 == idx2
