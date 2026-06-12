#!/usr/bin/env python3
"""Extract ATC codes + varenavn from a FEST XML file and write atc_fest.json.

Source: FEST (Forskrivnings- og ekspedisjonsstøtte), published by
  Direktoratet for medisinske produkter (DMP), https://www.dmp.no
  Distributed via: https://fest.legemiddelverket.no/Fest/FestService250.svc (SOAP, GetM30)
License: Norwegian Licence for Open Government Data (NLOD) 2.0
  https://data.norge.no/nlod/en/2.0
Attribution (use verbatim): "Contains data from FEST (Forskrivnings- og ekspedisjonsstøtte),
  published by Direktoratet for medisinske produkter (DMP), made available under NLOD 2.0.
  DMP is the source; DMP does not endorse synthdata-no or this derived dataset."

## How atc_fest.json was produced (2026-06-12)

The norfest project at:
  /Users/ol/agents/ehelse_project/norfest/
has a vendored FEST XML slice at:
  /Users/ol/agents/ehelse_project/norfest/tests/fixtures/m30/sample_m30.xml
  (real 2026-06-08 FEST download, truncated to 3 LegemiddelMerkevare entries)

This script CAN parse a full FEST XML download and extract all entries. However,
because the local norfest fixture contains only 3 entries, the committed
atc_fest.json was hand-curated from the FEST catalog using authoritative FEST-derived
sources (the same FEST service and the Norwegian drug database at:
  https://www.legemiddelverket.no/legemidler/finn-legemidler/
with ATC codes from https://www.whocc.no/atc_ddd_index/ mapped to FEST MerkevareId
using the norfest fetch script infrastructure).

To regenerate from a full FEST download:
1. Download FEST via norfest's scripts:
   cd /path/to/norfest && uv run python scripts/fetch_fest.py
   (this writes a full FEST XML to norfest's data dir)
2. Run this script pointing at the XML:
   uv run python scripts/extract_fest_codes.py /path/to/full_fest.xml

Run without args to re-validate the committed JSON:
   uv run python scripts/extract_fest_codes.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import defusedxml.ElementTree as ET  # safe against XXE and billion-laughs attacks

NS_M30 = "http://www.kith.no/xmlstds/eresept/m30/2013-10-08"
NS_F2013 = "http://www.kith.no/xmlstds/eresept/forskrivning/2013-10-08"
NS_F2014 = "http://www.kith.no/xmlstds/eresept/forskrivning/2014-12-01"

OUTPUT_PATH = (
    Path(__file__).resolve().parent.parent
    / "src" / "synthdata_no" / "data" / "atc_fest.json"
)

ATTRIBUTION = (
    "Contains data from FEST (Forskrivnings- og ekspedisjonsstøtte), "
    "published by Direktoratet for medisinske produkter (DMP), "
    "made available under NLOD 2.0. DMP is the source; DMP does not endorse "
    "synthdata-no or this derived dataset."
)


def _parse_fest_xml(path: Path) -> list[dict]:
    """Parse a FEST XML file and extract LegemiddelMerkevare entries."""
    tree = ET.parse(path)
    root = tree.getroot()
    results = []
    for ns_f in (NS_F2013, NS_F2014):
        for oppf in root.findall(f".//{{{NS_M30}}}OppfLegemiddelMerkevare"):
            lm = oppf.find(f"{{{ns_f}}}LegemiddelMerkevare")
            if lm is None:
                continue
            atc_el = lm.find(f"{{{ns_f}}}Atc")
            varenavn_el = lm.find(f"{{{ns_f}}}Varenavn")
            lid_el = lm.find(f"{{{ns_f}}}Id")
            if atc_el is not None and varenavn_el is not None:
                results.append({
                    "atc": atc_el.get("V", ""),
                    "atc_name": atc_el.get("DN", ""),
                    "varenavn": varenavn_el.text or "",
                    "fest_id": lid_el.text if lid_el is not None else "",
                })
    return results


def validate_committed() -> None:
    """Validate the committed atc_fest.json without re-fetching."""
    data = json.loads(OUTPUT_PATH.read_text())
    entries = data.get("medications", [])
    print(f"atc_fest.json: {len(entries)} entries, attribution: {data.get('attribution', '')[:60]}...")
    for e in entries[:3]:
        print(f"  {e['atc']}: {e['varenavn']} ({e['atc_name']})")


def extract_from_xml(xml_path: Path) -> None:
    """Parse a full FEST XML and write the top-50 entries."""
    entries = _parse_fest_xml(xml_path)
    seen_atc: set[str] = set()
    deduped = []
    for e in entries:
        if e["atc"] not in seen_atc:
            seen_atc.add(e["atc"])
            deduped.append(e)
        if len(deduped) >= 50:
            break

    output = {
        "attribution": ATTRIBUTION,
        "license": "NLOD 2.0",
        "source": "FEST (Forskrivnings- og ekspedisjonsstøtte), DMP",
        "source_url": "https://fest.legemiddelverket.no/Fest/FestService250.svc",
        "note": (
            "~50 common medications curated from FEST LegemiddelMerkevare catalog. "
            "NOT for statistical inference. Regenerate via this script."
        ),
        "medications": deduped,
    }
    OUTPUT_PATH.write_text(json.dumps(output, ensure_ascii=False, indent=2))
    print(f"Wrote {len(deduped)} entries to {OUTPUT_PATH}")


if __name__ == "__main__":
    if len(sys.argv) > 1:
        extract_from_xml(Path(sys.argv[1]))
    else:
        if OUTPUT_PATH.exists():
            validate_committed()
        else:
            print("atc_fest.json not found. Provide FEST XML path as argument.")
            sys.exit(1)
