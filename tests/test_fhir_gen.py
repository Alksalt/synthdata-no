"""Tests for synthdata_no.fhir_gen — FHIR R4B builders.

Validation layers:
  (a) R4B model_validate round-trip on every resource and the bundle.
  (b) fastjsonschema structural check on serialized bundle JSON.
"""
from __future__ import annotations

import json
import uuid

import fastjsonschema
import numpy as np
import pytest

from synthdata_no.codes import load_atc_fest, load_icd10_codes, load_loinc_min
from synthdata_no.fhir_gen import (
    _OID_DNR,
    _OID_FNR,
    _OID_ICD10_NO,
    _URI_ATC,
    _URI_FEST,
    _URI_LOINC,
    build_condition,
    build_medication,
    build_medication_request,
    build_medication_statement,
    build_observation,
    build_patient,
    build_transaction_bundle,
)
from synthdata_no.persons import generate_person

# ---------------------------------------------------------------------------
# JSON-schema validator (layer b) — compiled once per session
# ---------------------------------------------------------------------------
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
_COMPILED_BUNDLE_SCHEMA = fastjsonschema.compile(_BUNDLE_SCHEMA)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def rng() -> np.random.Generator:
    return np.random.default_rng(42)


@pytest.fixture
def rng2() -> np.random.Generator:
    return np.random.default_rng(42)


@pytest.fixture
def person(rng):
    return generate_person(rng=rng)


@pytest.fixture
def dnr_person():
    return generate_person(seed=7, dnr=True)


@pytest.fixture
def atc_entry():
    return load_atc_fest()[0]


@pytest.fixture
def icd10_entry():
    return load_icd10_codes()[0]


@pytest.fixture
def loinc_entry():
    # Creatinine entry
    entries = load_loinc_min()
    return next(e for e in entries if e.loinc == "2160-0")


# ---------------------------------------------------------------------------
# H1 — build_patient
# ---------------------------------------------------------------------------

class TestBuildPatient:
    def test_model_validate_round_trip(self, person, rng):
        """Layer (a): R4B model_validate + JSON round-trip."""
        from fhir.resources.R4B.patient import Patient

        patient, _ = build_patient(person, rng=rng)
        # Round-trip: dump → parse → validate
        dumped = json.loads(patient.model_dump_json())
        Patient.model_validate(dumped)

    def test_profile_set(self, person, rng):
        patient, _ = build_patient(person, rng=rng)
        assert patient.meta is not None
        assert "http://hl7.no/fhir/StructureDefinition/no-basis-Patient" in patient.meta.profile

    def test_fnr_identifier_system(self, person, rng):
        """fnr (not D-nr) gets OID 4.1."""
        patient, _ = build_patient(person, rng=rng)
        id_systems = [id_.system for id_ in patient.identifier]
        assert _OID_FNR in id_systems

    def test_dnr_identifier_system(self, dnr_person):
        """D-nr gets OID 4.2."""
        rng = np.random.default_rng(99)
        patient, _ = build_patient(dnr_person, rng=rng)
        id_systems = [id_.system for id_ in patient.identifier]
        assert _OID_DNR in id_systems

    def test_identifier_value_is_fnr(self, person, rng):
        patient, _ = build_patient(person, rng=rng)
        values = [id_.value for id_ in patient.identifier]
        assert person.fnr in values

    def test_gender_mapping_male(self):
        rng = np.random.default_rng(1)
        person = generate_person(rng=rng)
        # Find a male person
        for seed in range(50):
            p = generate_person(seed=seed)
            if p.sex == "M":
                rng_local = np.random.default_rng(seed + 1000)
                patient, _ = build_patient(p, rng=rng_local)
                assert patient.gender == "male"
                break

    def test_gender_mapping_female(self):
        for seed in range(50):
            p = generate_person(seed=seed)
            if p.sex == "F":
                rng_local = np.random.default_rng(seed + 1000)
                patient, _ = build_patient(p, rng=rng_local)
                assert patient.gender == "female"
                break

    def test_birth_date(self, person, rng):
        import datetime
        patient, _ = build_patient(person, rng=rng)
        # fhir.resources R4B returns birthDate as datetime.date, not string
        expected = person.birth_date
        actual = patient.birthDate
        if isinstance(actual, str):
            actual = datetime.date.fromisoformat(actual)
        assert actual == expected

    def test_address_postal_code(self, person, rng):
        patient, _ = build_patient(person, rng=rng)
        assert patient.address is not None
        assert len(patient.address) > 0
        assert patient.address[0].postalCode == person.postal_code

    def test_name_present(self, person, rng):
        patient, _ = build_patient(person, rng=rng)
        assert patient.name is not None
        assert len(patient.name) > 0
        name = patient.name[0]
        assert name.family is not None

    def test_uuid_returned(self, person, rng):
        _, res_uuid = build_patient(person, rng=rng)
        assert isinstance(res_uuid, uuid.UUID)

    def test_determinism(self, person):
        """Same person + same rng seed → same UUID."""
        _, uuid1 = build_patient(person, rng=np.random.default_rng(42))
        _, uuid2 = build_patient(person, rng=np.random.default_rng(42))
        assert uuid1 == uuid2


# ---------------------------------------------------------------------------
# H1 — build_medication
# ---------------------------------------------------------------------------

class TestBuildMedication:
    def test_model_validate_round_trip(self, atc_entry):
        from fhir.resources.R4B.medication import Medication

        rng = np.random.default_rng(42)
        med, _ = build_medication(atc_entry, rng=rng)
        dumped = json.loads(med.model_dump_json())
        Medication.model_validate(dumped)

    def test_both_codings_present(self, atc_entry):
        rng = np.random.default_rng(42)
        med, _ = build_medication(atc_entry, rng=rng)
        systems = {c.system for c in med.code.coding}
        assert _URI_FEST in systems
        assert _URI_ATC in systems

    def test_atc_code_correct(self, atc_entry):
        rng = np.random.default_rng(42)
        med, _ = build_medication(atc_entry, rng=rng)
        atc_coding = next(c for c in med.code.coding if c.system == _URI_ATC)
        assert atc_coding.code == atc_entry.atc

    def test_fest_code_uses_fest_id_when_present(self):
        """Entry with fest_id uses it; entry without falls back to ATC."""
        entries = load_atc_fest()
        entry_with_id = next(e for e in entries if e.fest_id)
        entry_without_id = next(e for e in entries if not e.fest_id)

        rng = np.random.default_rng(42)
        med_with, _ = build_medication(entry_with_id, rng=rng)
        rng2 = np.random.default_rng(43)
        med_without, _ = build_medication(entry_without_id, rng=rng2)

        fest_code_with = next(c.code for c in med_with.code.coding if c.system == _URI_FEST)
        assert fest_code_with == entry_with_id.fest_id

        fest_code_without = next(c.code for c in med_without.code.coding if c.system == _URI_FEST)
        assert fest_code_without == entry_without_id.atc  # fallback


# ---------------------------------------------------------------------------
# H1 — build_medication_statement / build_medication_request
# ---------------------------------------------------------------------------

class TestBuildMedicationStatementAndRequest:
    def test_medication_statement_round_trip(self, atc_entry):
        from fhir.resources.R4B.medicationstatement import MedicationStatement

        rng = np.random.default_rng(42)
        _, med_uuid = build_medication(atc_entry, rng=rng)
        ms, _ = build_medication_statement(
            "urn:uuid:patient-id", f"urn:uuid:{med_uuid}", rng=rng
        )
        MedicationStatement.model_validate(json.loads(ms.model_dump_json()))

    def test_medication_statement_references(self, atc_entry):
        rng = np.random.default_rng(42)
        _, med_uuid = build_medication(atc_entry, rng=rng)
        ms, _ = build_medication_statement(
            "urn:uuid:patient-id", f"urn:uuid:{med_uuid}", rng=rng
        )
        assert ms.subject.reference == "urn:uuid:patient-id"
        assert ms.medicationReference.reference == f"urn:uuid:{med_uuid}"

    def test_medication_statement_default_status(self, atc_entry):
        rng = np.random.default_rng(42)
        _, med_uuid = build_medication(atc_entry, rng=rng)
        ms, _ = build_medication_statement(
            "urn:uuid:p", f"urn:uuid:{med_uuid}", rng=rng
        )
        assert ms.status == "active"

    def test_medication_request_round_trip(self, atc_entry):
        from fhir.resources.R4B.medicationrequest import MedicationRequest

        rng = np.random.default_rng(42)
        _, med_uuid = build_medication(atc_entry, rng=rng)
        mr, _ = build_medication_request(
            "urn:uuid:patient-id", f"urn:uuid:{med_uuid}", rng=rng
        )
        MedicationRequest.model_validate(json.loads(mr.model_dump_json()))

    def test_medication_request_defaults(self, atc_entry):
        rng = np.random.default_rng(42)
        _, med_uuid = build_medication(atc_entry, rng=rng)
        mr, _ = build_medication_request(
            "urn:uuid:p", f"urn:uuid:{med_uuid}", rng=rng
        )
        assert mr.status == "active"
        assert mr.intent == "order"


# ---------------------------------------------------------------------------
# H1 — build_condition
# ---------------------------------------------------------------------------

class TestBuildCondition:
    def test_model_validate_round_trip(self, icd10_entry):
        from fhir.resources.R4B.condition import Condition

        rng = np.random.default_rng(42)
        cond, _ = build_condition("urn:uuid:patient", icd10_entry, rng=rng)
        Condition.model_validate(json.loads(cond.model_dump_json()))

    def test_icd10_system(self, icd10_entry):
        rng = np.random.default_rng(42)
        cond, _ = build_condition("urn:uuid:patient", icd10_entry, rng=rng)
        systems = [c.system for c in cond.code.coding]
        assert _OID_ICD10_NO in systems

    def test_no_display_field(self, icd10_entry):
        """ICD-10 coding must NOT carry a display field (licensing requirement)."""
        rng = np.random.default_rng(42)
        cond, _ = build_condition("urn:uuid:patient", icd10_entry, rng=rng)
        for coding in cond.code.coding:
            assert coding.display is None, (
                f"ICD-10 condition coding must not have display; got {coding.display!r}"
            )

    def test_code_value(self, icd10_entry):
        rng = np.random.default_rng(42)
        cond, _ = build_condition("urn:uuid:patient", icd10_entry, rng=rng)
        codes = [c.code for c in cond.code.coding]
        assert icd10_entry.code in codes

    def test_subject_reference(self, icd10_entry):
        rng = np.random.default_rng(42)
        cond, _ = build_condition("urn:uuid:patient-xyz", icd10_entry, rng=rng)
        assert cond.subject.reference == "urn:uuid:patient-xyz"


# ---------------------------------------------------------------------------
# H1 — build_observation
# ---------------------------------------------------------------------------

class TestBuildObservation:
    def test_model_validate_round_trip(self, loinc_entry):
        from fhir.resources.R4B.observation import Observation

        rng = np.random.default_rng(42)
        obs, _ = build_observation("urn:uuid:patient", loinc_entry, rng=rng)
        Observation.model_validate(json.loads(obs.model_dump_json()))

    def test_loinc_system(self, loinc_entry):
        rng = np.random.default_rng(42)
        obs, _ = build_observation("urn:uuid:patient", loinc_entry, rng=rng)
        systems = [c.system for c in obs.code.coding]
        assert _URI_LOINC in systems

    def test_loinc_code(self, loinc_entry):
        rng = np.random.default_rng(42)
        obs, _ = build_observation("urn:uuid:patient", loinc_entry, rng=rng)
        codes = [c.code for c in obs.code.coding]
        assert loinc_entry.loinc in codes

    def test_default_value_creatinine(self, loinc_entry):
        """Default creatinine value is 85.0 µmol/L (mid plausible range 50–130)."""
        rng = np.random.default_rng(42)
        obs, _ = build_observation("urn:uuid:patient", loinc_entry, rng=rng)
        assert obs.valueQuantity.value == loinc_entry.default_value

    def test_custom_value(self, loinc_entry):
        rng = np.random.default_rng(42)
        obs, _ = build_observation("urn:uuid:patient", loinc_entry, rng=rng, value=110.0, unit="umol/L")
        assert obs.valueQuantity.value == 110.0

    def test_status_default(self, loinc_entry):
        rng = np.random.default_rng(42)
        obs, _ = build_observation("urn:uuid:patient", loinc_entry, rng=rng)
        assert obs.status == "final"


# ---------------------------------------------------------------------------
# H1 — build_transaction_bundle
# ---------------------------------------------------------------------------

class TestBuildTransactionBundle:
    def _make_bundle(self):
        rng = np.random.default_rng(42)
        person = generate_person(rng=np.random.default_rng(1))
        atc = load_atc_fest()[0]
        icd10 = load_icd10_codes()[0]
        loinc = load_loinc_min()[0]

        patient, patient_uuid = build_patient(person, rng=rng)
        patient_ref = f"urn:uuid:{patient_uuid}"

        med, med_uuid = build_medication(atc, rng=rng)
        med_ref = f"urn:uuid:{med_uuid}"

        ms, ms_uuid = build_medication_statement(patient_ref, med_ref, rng=rng)
        cond, cond_uuid = build_condition(patient_ref, icd10, rng=rng)
        obs, obs_uuid = build_observation(patient_ref, loinc, rng=rng)

        resources = [
            (patient, patient_uuid),
            (med, med_uuid),
            (ms, ms_uuid),
            (cond, cond_uuid),
            (obs, obs_uuid),
        ]
        return build_transaction_bundle(resources), resources

    def test_model_validate_round_trip(self):
        """Layer (a): R4B Bundle model_validate round-trip."""
        from fhir.resources.R4B.bundle import Bundle

        bundle, _ = self._make_bundle()
        Bundle.model_validate(json.loads(bundle.model_dump_json()))

    def test_bundle_type_transaction(self):
        bundle, _ = self._make_bundle()
        assert bundle.type == "transaction"

    def test_all_entries_have_full_url(self):
        bundle, resources = self._make_bundle()
        for entry in bundle.entry:
            assert entry.fullUrl is not None
            assert entry.fullUrl.startswith("urn:uuid:")

    def test_all_entries_have_put_request(self):
        bundle, _ = self._make_bundle()
        for entry in bundle.entry:
            assert entry.request is not None
            assert entry.request.method == "PUT"
            assert "/" in entry.request.url

    def test_entry_count_matches_resources(self):
        bundle, resources = self._make_bundle()
        assert len(bundle.entry) == len(resources)

    def test_full_url_matches_resource_id(self):
        """fullUrl urn:uuid:X matches resource.id X."""
        bundle, _ = self._make_bundle()
        for entry in bundle.entry:
            res_id = json.loads(entry.resource.model_dump_json())["id"]
            assert entry.fullUrl == f"urn:uuid:{res_id}"

    def test_jsonschema_validation_layer_b(self):
        """Layer (b): fastjsonschema structural check on serialized JSON."""
        bundle, _ = self._make_bundle()
        bundle_dict = json.loads(bundle.model_dump_json())
        # Should not raise
        _COMPILED_BUNDLE_SCHEMA(bundle_dict)

    def test_put_url_contains_resource_type(self):
        bundle, _ = self._make_bundle()
        for entry in bundle.entry:
            resource_type = json.loads(entry.resource.model_dump_json())["resourceType"]
            assert entry.request.url.startswith(resource_type + "/")


# ---------------------------------------------------------------------------
# UUID determinism
# ---------------------------------------------------------------------------

class TestUUIDDeterminism:
    def test_same_seed_same_uuids(self):
        """Identical seed → identical UUIDs for patient and medication."""
        person = generate_person(seed=42)
        atc = load_atc_fest()[0]

        _, uuid1_p = build_patient(person, rng=np.random.default_rng(99))
        _, uuid1_m = build_medication(atc, rng=np.random.default_rng(99))

        _, uuid2_p = build_patient(person, rng=np.random.default_rng(99))
        _, uuid2_m = build_medication(atc, rng=np.random.default_rng(99))

        assert uuid1_p == uuid2_p
        assert uuid1_m == uuid2_m

    def test_different_seeds_different_uuids(self):
        person = generate_person(seed=42)
        _, uuid1 = build_patient(person, rng=np.random.default_rng(1))
        _, uuid2 = build_patient(person, rng=np.random.default_rng(2))
        assert uuid1 != uuid2
