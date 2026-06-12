"""No-trap baseline FHIR fixture scaffold for fhir-safety-harness.

Exports a no-trap patient bundle that fhir-safety-harness uses as the baseline
(safe, non-triggered) fixture. Trap CONTENT (hallucinations, wrong doses,
dangerous drug pairs, guideline violations) is owner-authored in the
``fhir-safety-harness`` project — never generated here. This module only
produces structurally valid, clinically neutral synthetic bundles.

Honesty framing
---------------
Generated bundles contain no real persons and carry no re-identification risk
by construction. They are NOT for statistical inference about Norwegian patient
populations. See ``PHYSICIAN_REVIEW.md`` for the owner sign-off checklist that
gates any realism claim.

UUID determinism
----------------
All UUIDs are derived via ``fhir_gen._make_uuid(rng)`` — seeded numpy Generator,
byte-identical output for the same seed across runs.
"""
from __future__ import annotations

import importlib.metadata
import json
import uuid
from pathlib import Path
from typing import Optional

import numpy as np

from synthdata_no.codes import ATCEntry, ICD10Entry, LOINCEntry, load_atc_fest, load_icd10_codes, load_loinc_min
from synthdata_no.fhir_gen import (
    build_condition,
    build_medication,
    build_medication_statement,
    build_observation,
    build_patient,
    build_transaction_bundle,
)
from synthdata_no.persons import Person, generate_persons


def patient_bundle(
    person: Person,
    *,
    meds: Optional[list[ATCEntry]] = None,
    conditions: Optional[list[ICD10Entry]] = None,
    observations: Optional[list[tuple[LOINCEntry, float, str]]] = None,
    rng: np.random.Generator,
) -> object:  # returns fhir.resources.R4B.bundle.Bundle
    """Build a transaction Bundle for one synthetic patient.

    This is the no-trap baseline scaffold consumed by fhir-safety-harness.
    Trap content (e.g., dangerous drug interactions, wrong doses) is
    owner-authored in fhir-safety-harness, never generated here.

    Args:
        person: A synthetic Person (Tenor-range fnr/D-nr).
        meds: ATC entries to include as Medication + MedicationStatement pairs.
            If None, no medication resources are added.
        conditions: ICD-10 entries to include as Condition resources.
            If None, no conditions are added.
        observations: List of ``(LOINCEntry, value, unit)`` tuples for
            Observation resources. If None, no observations are added.
        rng: Seeded numpy Generator — all UUIDs derived from this.

    Returns:
        A validated R4B Bundle (transaction type).
    """
    resources: list[tuple[object, uuid.UUID]] = []

    # Patient
    patient, patient_uuid = build_patient(person, rng=rng)
    patient_ref = f"urn:uuid:{patient_uuid}"
    resources.append((patient, patient_uuid))

    # Medications → Medication + MedicationStatement pairs
    for atc_entry in (meds or []):
        med, med_uuid = build_medication(atc_entry, rng=rng)
        med_ref = f"urn:uuid:{med_uuid}"
        resources.append((med, med_uuid))

        ms, ms_uuid = build_medication_statement(
            patient_ref, med_ref, rng=rng
        )
        resources.append((ms, ms_uuid))

    # Conditions
    for icd10_entry in (conditions or []):
        cond, cond_uuid = build_condition(patient_ref, icd10_entry, rng=rng)
        resources.append((cond, cond_uuid))

    # Observations
    for loinc_entry, value, unit in (observations or []):
        obs, obs_uuid = build_observation(
            patient_ref, loinc_entry, rng=rng, value=value, unit=unit
        )
        resources.append((obs, obs_uuid))

    return build_transaction_bundle(resources)


def write_fixture_set(
    out_dir: Path,
    n_patients: int,
    seed: int,
) -> None:
    """Write one JSON bundle per patient plus an index.json.

    The fixture set is byte-deterministic: same ``seed`` and ``n_patients``
    → identical JSON files across runs.

    Output layout::

        out_dir/
          patient_0000.json
          ...
          patient_NNNN.json
          index.json

    ``index.json`` contains:
      - ``seed``: the seed used
      - ``n_patients``: number of patients
      - ``package_version``: synthdata-no version
      - ``counts``: per-resource-type counts for the last bundle (representative)

    Args:
        out_dir: Directory to write into (created if absent).
        n_patients: Number of patient bundles to generate.
        seed: Integer seed for full determinism.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    rng = np.random.default_rng(seed)
    persons = generate_persons(n_patients, seed)

    atc_entries = load_atc_fest()
    icd10_entries = load_icd10_codes()
    loinc_entries = load_loinc_min()

    # Creatinine entry for observations
    creatinine = next((e for e in loinc_entries if e.loinc == "2160-0"), loinc_entries[0])

    last_counts: dict[str, int] = {}

    for i, person in enumerate(persons):
        # Per-patient seeded variety: 1–3 meds, 1–3 conditions, jittered creatinine
        # Each patient gets a distinct sub-rng derived from the main rng so clinical
        # content varies while remaining byte-deterministic across runs.
        n_meds = int(rng.integers(1, 4))           # 1, 2, or 3
        n_conditions = int(rng.integers(1, 4))     # 1, 2, or 3
        med_indices = rng.choice(len(atc_entries), size=n_meds, replace=False)
        cond_indices = rng.choice(len(icd10_entries), size=n_conditions, replace=False)
        _meds = [atc_entries[j] for j in sorted(med_indices)]
        _conditions = [icd10_entries[j] for j in sorted(cond_indices)]
        creatinine_value = round(
            float(np.clip(rng.normal(85, 18), 50, 110)), 1
        )
        _observations = [(creatinine, creatinine_value, creatinine.unit)]

        bundle = patient_bundle(
            person,
            meds=_meds,
            conditions=_conditions,
            observations=_observations,
            rng=rng,
        )
        bundle_json = json.loads(bundle.model_dump_json())

        # Count resource types
        counts: dict[str, int] = {}
        for entry in bundle_json.get("entry", []):
            rt = entry.get("resource", {}).get("resourceType", "Unknown")
            counts[rt] = counts.get(rt, 0) + 1
        last_counts = counts

        out_path = out_dir / f"patient_{i:04d}.json"
        out_path.write_text(json.dumps(bundle_json, indent=2, ensure_ascii=False), encoding="utf-8")

    index = {
        "seed": seed,
        "n_patients": n_patients,
        "package_version": importlib.metadata.version("synthdata-no"),
        "counts": last_counts,
    }
    (out_dir / "index.json").write_text(
        json.dumps(index, indent=2, ensure_ascii=False), encoding="utf-8"
    )
