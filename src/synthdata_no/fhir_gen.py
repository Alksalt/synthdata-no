"""FHIR R4B resource builders for synthetic Norwegian health data.

Module name ``fhir_gen`` avoids shadowing the ``fhir.resources`` library.

No-basis profile note
---------------------
This module targets ``hl7.fhir.no.basis`` patterns (identifier OIDs, coding systems,
meta.profile URL) but does NOT perform full no-basis IG validation — that would require
resolving the no-basis IG from Simplifier at runtime, which is the consumer's release
gate (see fhir-safety-harness).

Offline validation in tests
----------------------------
Two layers are applied in the test suite:
  (a) R4B ``model_validate`` round-trip on every built resource and the bundle — catches
      field-type, cardinality, and enum violations via pydantic v2.
  (b) ``fastjsonschema`` (bundled by the ``fhir-validator`` PyPI package) on the
      serialized bundle JSON — an independent structural check.

Full no-basis profile validation (hl7.fhir.no.basis 2.2.2 via Simplifier) is the
consumer's responsibility at release time. No validator_cli.jar is used here.

UUID determinism scheme
-----------------------
All resource UUIDs are derived from a seeded numpy Generator via::

    uuid.UUID(bytes=rng.bytes(16), version=4)

This guarantees byte-identical output for the same seed. Never use ``uuid.uuid4()``
(which draws from the OS entropy pool) on the default path.
"""
from __future__ import annotations

import json
import uuid
import datetime
from typing import Optional

import numpy as np

from fhir.resources.R4B.bundle import Bundle
from fhir.resources.R4B.condition import Condition
from fhir.resources.R4B.medication import Medication
from fhir.resources.R4B.medicationrequest import MedicationRequest
from fhir.resources.R4B.medicationstatement import MedicationStatement
from fhir.resources.R4B.observation import Observation
from fhir.resources.R4B.patient import Patient

from synthdata_no.codes import ATCEntry, ICD10Entry, LOINCEntry
from synthdata_no.ids import is_synthetic_fnr
from synthdata_no.kommuner import kommune_name
from synthdata_no.persons import Person

# ---------------------------------------------------------------------------
# Coding system URIs (no-basis canonical references)
# ---------------------------------------------------------------------------

_OID_FNR = "urn:oid:2.16.578.1.12.4.1.4.1"
_OID_DNR = "urn:oid:2.16.578.1.12.4.1.4.2"
_OID_ICD10_NO = "urn:oid:2.16.578.1.12.4.1.1.7110"
_URI_FEST = "http://ehelse.no/fhir/CodeSystem/FEST"
_URI_ATC = "http://www.whocc.no/atc"
_URI_LOINC = "http://loinc.org"
_URI_UCUM = "http://unitsofmeasure.org"
_PROFILE_NO_BASIS_PATIENT = (
    "http://hl7.no/fhir/StructureDefinition/no-basis-Patient"
)

# Gender map: Person.sex → FHIR gender code
_SEX_TO_GENDER = {"M": "male", "F": "female"}


# ---------------------------------------------------------------------------
# UUID helper
# ---------------------------------------------------------------------------

def _make_uuid(rng: np.random.Generator) -> uuid.UUID:
    """Derive a deterministic UUID from a seeded numpy Generator.

    Uses ``rng.bytes(16)`` so the UUID is fully determined by the rng state.
    The ``version=4`` flag sets the variant/version bits per RFC 4122 while
    keeping the remaining 122 bits from the rng stream.
    """
    return uuid.UUID(bytes=bytes(rng.bytes(16)), version=4)


def _urn(u: uuid.UUID) -> str:
    return f"urn:uuid:{u}"


# ---------------------------------------------------------------------------
# D-nr detection helper
# ---------------------------------------------------------------------------

def _is_dnr(identifier: str) -> bool:
    """Return True if the identifier is a D-number (day 41–71)."""
    if not isinstance(identifier, str) or len(identifier) != 11:
        return False
    day = int(identifier[:2])
    return 41 <= day <= 71


# ---------------------------------------------------------------------------
# H1 Builders
# ---------------------------------------------------------------------------

def build_patient(person: Person, *, rng: np.random.Generator) -> tuple[Patient, uuid.UUID]:
    """Build a no-basis-Patient from a synthetic Person.

    Args:
        person: A synthetic Person record (Tenor-range fnr or D-nr).
        rng: Seeded Generator — used to derive the resource UUID.

    Returns:
        (Patient, resource_uuid) — caller owns the uuid for bundle assembly.
    """
    resource_id = _make_uuid(rng)

    # Identifier system: OID for fnr vs D-nr
    id_system = _OID_DNR if _is_dnr(person.fnr) else _OID_FNR

    # Name: split «Fornavn [Mellomnavn] Etternavn» — last token = family
    name_parts = person.name.split()
    family = name_parts[-1] if name_parts else person.name
    given = name_parts[:-1] if len(name_parts) > 1 else [person.name]

    patient_dict = {
        "resourceType": "Patient",
        "id": str(resource_id),
        "meta": {
            "profile": [_PROFILE_NO_BASIS_PATIENT],
        },
        "identifier": [
            {
                "system": id_system,
                "value": person.fnr,
            }
        ],
        "name": [
            {
                "family": family,
                "given": given,
            }
        ],
        "gender": _SEX_TO_GENDER.get(person.sex, "unknown"),
        "birthDate": person.birth_date.isoformat(),
        "address": [
            {
                "line": [person.address],
                "postalCode": person.postal_code,
                # city: resolve kommune NAME from KLASS snapshot (P2)
                # kommune CODE is kept in identifiers, not leaked into city
                "city": kommune_name(person.kommune) or person.kommune,
                "country": "NO",
            }
        ],
    }

    return Patient.model_validate(patient_dict), resource_id


def build_medication(atc_entry: ATCEntry, *, rng: np.random.Generator) -> tuple[Medication, uuid.UUID]:
    """Build a Medication resource with BOTH FEST and ATC codings.

    no-basis-Medication requires the FEST slice (min:1). ATC is the second coding.
    ``display`` is set to ``varenavn`` (NLOD-clean from FEST).

    For entries without a ``fest_id``, the ``atc`` code is used as the FEST code
    value (documents the limitation — full FEST IDs require a live FEST download).

    Args:
        atc_entry: An ATCEntry from ``codes.load_atc_fest()``.
        rng: Seeded Generator for UUID derivation.

    Returns:
        (Medication, resource_uuid)
    """
    resource_id = _make_uuid(rng)
    # Use FEST ID if present, otherwise fall back to ATC code as the FEST identifier
    fest_code = atc_entry.fest_id if atc_entry.fest_id else atc_entry.atc

    med_dict = {
        "resourceType": "Medication",
        "id": str(resource_id),
        "code": {
            "coding": [
                {
                    "system": _URI_FEST,
                    "code": fest_code,
                    "display": atc_entry.varenavn,
                },
                {
                    "system": _URI_ATC,
                    "code": atc_entry.atc,
                    "display": atc_entry.varenavn,
                },
            ]
        },
    }
    return Medication.model_validate(med_dict), resource_id


def build_medication_statement(
    patient_ref: str,
    medication_ref: str,
    *,
    rng: np.random.Generator,
    status: str = "active",
) -> tuple[MedicationStatement, uuid.UUID]:
    """Build a MedicationStatement linking patient to medication.

    Args:
        patient_ref: ``urn:uuid:…`` reference to the Patient entry.
        medication_ref: ``urn:uuid:…`` reference to the Medication entry.
        rng: Seeded Generator.
        status: FHIR status code (default ``"active"``).

    Returns:
        (MedicationStatement, resource_uuid)
    """
    resource_id = _make_uuid(rng)
    ms_dict = {
        "resourceType": "MedicationStatement",
        "id": str(resource_id),
        "status": status,
        "subject": {"reference": patient_ref},
        "medicationReference": {"reference": medication_ref},
    }
    return MedicationStatement.model_validate(ms_dict), resource_id


def build_medication_request(
    patient_ref: str,
    medication_ref: str,
    *,
    rng: np.random.Generator,
    status: str = "active",
    intent: str = "order",
) -> tuple[MedicationRequest, uuid.UUID]:
    """Build a MedicationRequest linking patient to medication.

    Args:
        patient_ref: ``urn:uuid:…`` reference to the Patient entry.
        medication_ref: ``urn:uuid:…`` reference to the Medication entry.
        rng: Seeded Generator.
        status: FHIR status code (default ``"active"``).
        intent: FHIR intent code (default ``"order"``).

    Returns:
        (MedicationRequest, resource_uuid)
    """
    resource_id = _make_uuid(rng)
    mr_dict = {
        "resourceType": "MedicationRequest",
        "id": str(resource_id),
        "status": status,
        "intent": intent,
        "subject": {"reference": patient_ref},
        "medicationReference": {"reference": medication_ref},
    }
    return MedicationRequest.model_validate(mr_dict), resource_id


def build_condition(
    patient_ref: str,
    icd10_entry: ICD10Entry,
    *,
    rng: np.random.Generator,
) -> tuple[Condition, uuid.UUID]:
    """Build a Condition with ICD-10-NO coding (code only, no display).

    Coding system: ``urn:oid:2.16.578.1.12.4.1.1.7110`` (ICD-10-NO OID).
    The ``display`` field is intentionally omitted — embedding Norwegian display
    names would be an uncleared adaptation under WHO CC BY-ND 3.0 IGO.

    Args:
        patient_ref: ``urn:uuid:…`` reference to the Patient.
        icd10_entry: An ICD10Entry from ``codes.load_icd10_codes()``.
        rng: Seeded Generator.

    Returns:
        (Condition, resource_uuid)
    """
    resource_id = _make_uuid(rng)
    condition_dict = {
        "resourceType": "Condition",
        "id": str(resource_id),
        "subject": {"reference": patient_ref},
        "code": {
            "coding": [
                {
                    "system": _OID_ICD10_NO,
                    "code": icd10_entry.code,
                    # display intentionally absent — see module docstring
                }
            ]
        },
    }
    return Condition.model_validate(condition_dict), resource_id


def build_observation(
    patient_ref: str,
    loinc_entry: LOINCEntry,
    *,
    rng: np.random.Generator,
    value: Optional[float] = None,
    unit: Optional[str] = None,
    status: str = "final",
) -> tuple[Observation, uuid.UUID]:
    """Build an Observation with a LOINC code and a quantitative value.

    Defaults to the LOINC entry's ``default_value`` and ``unit``.
    For creatinine (2160-0), the plausible range is 50–130 µmol/L;
    the default_value (85.0 µmol/L) is mid-range.

    Args:
        patient_ref: ``urn:uuid:…`` reference to the Patient.
        loinc_entry: A LOINCEntry from ``codes.load_loinc_min()``.
        rng: Seeded Generator.
        value: Numeric result (defaults to ``loinc_entry.default_value``).
        unit: Unit string (defaults to ``loinc_entry.unit``).
        status: FHIR observation status (default ``"final"``).

    Returns:
        (Observation, resource_uuid)
    """
    resource_id = _make_uuid(rng)
    obs_value = value if value is not None else loinc_entry.default_value
    obs_unit = unit if unit is not None else loinc_entry.unit

    # Use UCUM code for valueQuantity.code (machine-readable); unit is for display
    ucum_code = loinc_entry.ucum if unit is None else obs_unit

    obs_dict = {
        "resourceType": "Observation",
        "id": str(resource_id),
        "status": status,
        "subject": {"reference": patient_ref},
        "code": {
            "coding": [
                {
                    "system": _URI_LOINC,
                    "code": loinc_entry.loinc,
                    "display": loinc_entry.component,
                }
            ]
        },
        "valueQuantity": {
            "value": obs_value,
            "unit": obs_unit,   # human-readable display unit
            "system": _URI_UCUM,
            "code": ucum_code,  # UCUM machine code (from loinc_entry.ucum)
        },
    }
    return Observation.model_validate(obs_dict), resource_id


# ---------------------------------------------------------------------------
# H1 Bundle builder
# ---------------------------------------------------------------------------

def build_transaction_bundle(
    resources: list[tuple[object, uuid.UUID]],
) -> Bundle:
    """Assemble a transaction Bundle from (resource, uuid) pairs.

    Each entry gets:
      - ``fullUrl``: ``urn:uuid:<uuid>``
      - ``request``: ``{method: PUT, url: <ResourceType>/<id>}``

    Intra-bundle references use ``urn:uuid:…`` fullUrls consistently —
    callers must pass the same UUID that was embedded as ``reference`` in
    subject/medicationReference fields.

    Args:
        resources: List of ``(fhir_resource, uuid)`` pairs — same UUID that
            the builder returned and that callers used for references.

    Returns:
        A validated R4B Bundle.
    """
    entries = []
    for resource, res_uuid in resources:
        resource_type = resource.__class__.__name__
        full_url = _urn(res_uuid)
        entry = {
            "fullUrl": full_url,
            "resource": json.loads(resource.model_dump_json()),
            "request": {
                "method": "PUT",
                "url": f"{resource_type}/{res_uuid}",
            },
        }
        entries.append(entry)

    bundle_dict = {
        "resourceType": "Bundle",
        "type": "transaction",
        "entry": entries,
    }
    return Bundle.model_validate(bundle_dict)
