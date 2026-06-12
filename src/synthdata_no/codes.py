"""Typed registries for embedded code lists.

Three embedded lists shipped with the package:
  - ATC codes + varenavn from FEST (NLOD 2.0, attribute DMP)
  - LOINC subset (Regenstrief attribution notice required)
  - ICD-10 codes WITHOUT Norwegian display names (user-supplied display supported)

Attribution notices are embedded in the JSON files and must be preserved
in any derived artifact. See THIRD_PARTY_SOURCES.md.

ICD-10 license note: alphanumeric codes only (no Norwegian or English display
names embedded). Norwegian display names are an uncleared adaptation under WHO
CC BY-ND 3.0 IGO. User-supplied display files are supported via load_icd10_codes().
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from importlib.resources import files
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ATCEntry:
    """One medication entry from the FEST-derived ATC registry."""
    atc: str
    atc_name: str
    varenavn: str
    fest_id: str = ""


@dataclass(frozen=True)
class LOINCEntry:
    """One LOINC observation code (Regenstrief)."""
    loinc: str
    component: str
    system: str
    scale: str
    unit: str
    default_value: float
    reference_range: str = ""


@dataclass(frozen=True)
class ICD10Entry:
    """One ICD-10 code (alphanumeric only, no display text embedded)."""
    code: str
    chapter: str
    display: Optional[str] = field(default=None, compare=False)


# ---------------------------------------------------------------------------
# Loaders
# ---------------------------------------------------------------------------

@lru_cache(maxsize=1)
def load_atc_fest() -> list[ATCEntry]:
    """Load the FEST-derived ATC medication registry.

    Attribution: Contains data from FEST (Forskrivnings- og ekspedisjonsstøtte),
    published by Direktoratet for medisinske produkter (DMP), made available under
    NLOD 2.0. DMP is the source; DMP does not endorse synthdata-no or this derived
    dataset.

    Returns:
        List of ATCEntry objects sorted by ATC code.
    """
    data = json.loads(
        files("synthdata_no.data").joinpath("atc_fest.json").read_text(encoding="utf-8")
    )
    return [
        ATCEntry(
            atc=m["atc"],
            atc_name=m["atc_name"],
            varenavn=m["varenavn"],
            fest_id=m.get("fest_id", ""),
        )
        for m in data["medications"]
    ]


@lru_cache(maxsize=1)
def load_loinc_min() -> list[LOINCEntry]:
    """Load the minimal LOINC observation code set.

    Attribution: This content includes LOINC codes. LOINC® is a registered
    trademark of Regenstrief Institute, Inc. © 1995 Regenstrief Institute, Inc.
    License: https://loinc.org/license/

    Returns:
        List of LOINCEntry objects.
    """
    data = json.loads(
        files("synthdata_no.data").joinpath("loinc_min.json").read_text(encoding="utf-8")
    )
    return [
        LOINCEntry(
            loinc=c["loinc"],
            component=c["component"],
            system=c["system"],
            scale=c["scale"],
            unit=c["unit"],
            default_value=float(c["default_value"]),
            reference_range=c.get("reference_range", ""),
        )
        for c in data["codes"]
    ]


def load_icd10_codes(
    display_file: Optional[Path] = None,
) -> list[ICD10Entry]:
    """Load the ICD-10 code registry (codes only, no display text embedded).

    ICD-10 codes are redistributed under WHO CC BY-ND 3.0 IGO (code-only;
    Norwegian display names are a separate uncleared translation — never embed them).
    Source: WHO ICD-10 Version 2019, https://icd.who.int/browse10/

    Args:
        display_file: Optional path to a JSON file mapping code → display string.
            This allows callers to supply their own display translations without
            embedding them in the package.

    Returns:
        List of ICD10Entry objects; display is None unless display_file is given.
    """
    data = json.loads(
        files("synthdata_no.data").joinpath("icd10_codes.json").read_text(encoding="utf-8")
    )

    display_map: dict[str, str] = {}
    if display_file is not None:
        display_map = json.loads(Path(display_file).read_text(encoding="utf-8"))

    return [
        ICD10Entry(
            code=c["code"],
            chapter=c["chapter"],
            display=display_map.get(c["code"]),
        )
        for c in data["codes"]
    ]
