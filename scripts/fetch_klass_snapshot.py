#!/usr/bin/env python3
"""Fetch SSB KLASS classification 131 (kommuner) and write committed snapshot.

Source: https://klass.ssb.no — classification 131 (Kommuner i Norge)
License: Norsk lisens for offentlige data (NLOD) 2.0 / CC BY 4.0 (SSB)
Attribution: Statistics Norway (SSB), klass.ssb.no, classification 131.

Run:
    uv run python scripts/fetch_klass_snapshot.py

Writes to: src/synthdata_no/data/klass_131_snapshot.json
"""
from __future__ import annotations

import datetime
import json
import sys
from pathlib import Path

import requests

KLASS_URL = (
    "https://data.ssb.no/api/klass/v1/classifications/131/codesAt"
    "?date={ref_date}"
)

OUTPUT_PATH = (
    Path(__file__).resolve().parent.parent
    / "src" / "synthdata_no" / "data" / "klass_131_snapshot.json"
)

KLASS_CLASSIFICATION_URL = "https://data.ssb.no/api/klass/v1/classifications/131"


def fetch(ref_date: str = "2024-01-01") -> list[dict]:
    """Fetch valid kommuner codes from KLASS API as of the given date."""
    url = KLASS_URL.format(ref_date=ref_date)
    print(f"Fetching: {url}", file=sys.stderr)
    resp = requests.get(url, timeout=30, headers={"Accept": "application/json"})
    resp.raise_for_status()
    data = resp.json()
    return data.get("codes", [])


def main() -> None:
    today = datetime.date.today().isoformat()
    # Use a stable reference date so snapshot is reproducible
    ref_date = "2024-01-01"
    codes_raw = fetch(ref_date)

    kommuner: list[dict] = []
    for entry in codes_raw:
        code = entry.get("code", "")
        name = entry.get("name", "")
        if code and len(code) == 4 and code.isdigit():
            kommuner.append({"code": code, "name": name})

    kommuner.sort(key=lambda x: x["code"])

    snapshot = {
        "date": today,
        "reference_date": ref_date,
        "source": "https://data.ssb.no/api/klass/v1/classifications/131",
        "license": "NLOD 2.0 / CC BY 4.0 — Statistics Norway (SSB)",
        "attribution": "Statistics Norway (SSB), data.ssb.no/api/klass, classification 131 (Kommuner i Norge)",
        "count": len(kommuner),
        "kommuner": kommuner,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2))
    print(
        f"Wrote {len(kommuner)} kommuner to {OUTPUT_PATH}",
        file=sys.stderr,
    )


if __name__ == "__main__":
    main()
