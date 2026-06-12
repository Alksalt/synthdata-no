"""synthdata-no — deterministic generator of synthetic Norwegian health data.

Families:
  - ids: Tenor-range synthetic fødselsnummer and D-nummer
  - kommuner: SSB KLASS-backed kommune code registry
  - codes: ATC/FEST, LOINC, and ICD-10 code registries
  - persons: Person dataclass + seeded generator

No real persons. No re-identification risk by construction.
NOT for statistical inference about the Norwegian population.
"""

from synthdata_no.codes import ATCEntry, ICD10Entry, LOINCEntry, load_atc_fest, load_icd10_codes, load_loinc_min
from synthdata_no.ids import fnr_birth_date, is_synthetic_fnr, synthetic_dnr, synthetic_fnr, valid_fnr_checksum
from synthdata_no.kommuner import random_kommune, valid_kommune_codes
from synthdata_no.persons import Person, generate_person, generate_persons

__all__ = [
    # ids
    "synthetic_fnr",
    "synthetic_dnr",
    "is_synthetic_fnr",
    "fnr_birth_date",
    "valid_fnr_checksum",
    # kommuner
    "valid_kommune_codes",
    "random_kommune",
    # codes
    "ATCEntry",
    "LOINCEntry",
    "ICD10Entry",
    "load_atc_fest",
    "load_loinc_min",
    "load_icd10_codes",
    # persons
    "Person",
    "generate_person",
    "generate_persons",
]
