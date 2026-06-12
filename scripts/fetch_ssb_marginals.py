#!/usr/bin/env python3
"""Fetch SSB 07459 (Befolkning etter region, kjønn, alder) marginals snapshot.

Queries the SSB PxWeb API for age 18–95 × sex × kommune (4-digit codes only),
for the reference year 2024. Aggregates to a committed parquet snapshot used by
tabular.py for kommune-conditional age/sex marginals.

Source: Statistics Norway (SSB), data.ssb.no/api/v0/no/table/07459
License: CC BY 4.0 — Statistics Norway (SSB)
Reference year: 2024 (most recent complete year as of snapshot date)

Run:
    uv run python scripts/fetch_ssb_marginals.py

Writes to: src/synthdata_no/data/ssb_07459_snapshot.parquet

Column schema:
    kommune (str, 4-digit) | age (int, 18–95) | sex (int, 1=M / 2=F) | count (int)

Data-source path:
    LIVE FETCH from SSB PxWeb API (not reusing omsorgsradar cache — the
    omsorgsradar/data/cache/07459.json cache only covers ages 80–104 for a
    different query, so we fetch the full 18–95 range directly).

KLASS overlap:
    All 358 terminal-2024 KLASS-131 kommune codes are present in SSB 07459.
    Any municipality codes in 07459 that are not in the KLASS snapshot are
    excluded (they are historical/aggregate codes); overlap documented below.
"""
from __future__ import annotations

import datetime
import json
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = REPO_ROOT / "src" / "synthdata_no" / "data" / "ssb_07459_snapshot.parquet"
KLASS_SNAPSHOT = REPO_ROOT / "src" / "synthdata_no" / "data" / "klass_131_snapshot.json"

SSB_API_URL = "https://data.ssb.no/api/v0/no/table/07459"
REFERENCE_YEAR = "2024"
AGE_RANGE = range(18, 96)  # 18 to 95 inclusive
USER_AGENT = "synthdata-no/0.1 (github.com/Alksalt/synthdata-no; research use)"

# Sex codes in SSB 07459: 1=Menn, 2=Kvinner
SEX_CODES = ["1", "2"]


def load_klass_codes() -> list[str]:
    """Load terminal 2024 KLASS-131 kommune codes."""
    with KLASS_SNAPSHOT.open(encoding="utf-8") as f:
        snap = json.load(f)
    return [e["code"] for e in snap["kommuner"]]


def _post_json(url: str, payload: dict, max_retries: int = 3) -> dict:
    """POST JSON to SSB PxWeb API with retry."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": USER_AGENT,
        },
        method="POST",
    )
    for attempt in range(max_retries):
        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                return json.load(resp)
        except urllib.error.URLError as exc:
            if attempt < max_retries - 1:
                wait = 5 * (attempt + 1)
                print(f"  Retry {attempt + 1}/{max_retries} after {wait}s: {exc}", file=sys.stderr)
                time.sleep(wait)
            else:
                raise
    raise RuntimeError("unreachable")


def fetch_marginals(klass_codes: list[str]) -> list[dict]:
    """Fetch age × sex × kommune counts from SSB 07459 for REFERENCE_YEAR.

    Batches the request to keep payload size manageable.
    Returns list of {kommune, age, sex, count} dicts.
    """
    age_codes = [f"{a:03d}" for a in AGE_RANGE]  # "018" … "095"

    payload = {
        "query": [
            {
                "code": "Region",
                "selection": {"filter": "item", "values": klass_codes},
            },
            {
                "code": "Kjonn",
                "selection": {"filter": "item", "values": SEX_CODES},
            },
            {
                "code": "Alder",
                "selection": {"filter": "item", "values": age_codes},
            },
            {
                "code": "ContentsCode",
                "selection": {"filter": "item", "values": ["Personer1"]},
            },
            {
                "code": "Tid",
                "selection": {"filter": "item", "values": [REFERENCE_YEAR]},
            },
        ],
        "response": {"format": "json-stat2"},
    }

    print(
        f"Fetching {len(klass_codes)} kommuner × {len(age_codes)} ages × 2 sexes "
        f"for year {REFERENCE_YEAR} …",
        file=sys.stderr,
    )

    raw = _post_json(SSB_API_URL, payload)

    # Decode JSON-stat2: size order = Region × Kjonn × Alder × Contents × Tid
    dims = raw["dimension"]
    region_keys = list(dims["Region"]["category"]["index"].keys())
    kjonn_keys = list(dims["Kjonn"]["category"]["index"].keys())
    alder_keys = list(dims["Alder"]["category"]["index"].keys())
    values = raw["value"]

    n_region = len(region_keys)
    n_sex = len(kjonn_keys)
    n_age = len(alder_keys)
    # Expecting n_region × n_sex × n_age × 1 × 1

    if len(values) != n_region * n_sex * n_age:
        raise RuntimeError(
            f"Unexpected value count: {len(values)} != {n_region}×{n_sex}×{n_age}="
            f"{n_region * n_sex * n_age}"
        )

    rows = []
    idx = 0
    for ri, region_code in enumerate(region_keys):
        for si, sex_code in enumerate(kjonn_keys):
            for ai, age_code in enumerate(alder_keys):
                count = values[idx]
                idx += 1
                rows.append(
                    {
                        "kommune": region_code,
                        "age": int(age_code),
                        "sex": int(sex_code),
                        "count": int(count) if count is not None else 0,
                    }
                )
    return rows


def main() -> None:
    import pandas as pd

    klass_codes = load_klass_codes()
    print(f"Loaded {len(klass_codes)} KLASS-131 codes", file=sys.stderr)

    rows = fetch_marginals(klass_codes)
    df = pd.DataFrame(rows)

    total_rows = len(df)
    total_pop = int(df["count"].sum())
    zero_rows = int((df["count"] == 0).sum())
    print(
        f"Fetched {total_rows} rows; total population={total_pop:,}; "
        f"zero-count cells={zero_rows}",
        file=sys.stderr,
    )

    # Verification: all kommune codes must be in KLASS set
    klass_set = set(klass_codes)
    fetched_komunner = set(df["kommune"].unique())
    not_in_klass = fetched_komunner - klass_set
    if not_in_klass:
        print(
            f"WARNING: {len(not_in_klass)} fetched codes not in KLASS: {sorted(not_in_klass)[:5]}",
            file=sys.stderr,
        )
    overlap_pct = len(fetched_komunner & klass_set) / len(klass_set) * 100
    print(f"KLASS overlap: {overlap_pct:.1f}%", file=sys.stderr)

    # Attach metadata as parquet schema metadata
    metadata = {
        "source": SSB_API_URL,
        "table": "07459",
        "reference_year": REFERENCE_YEAR,
        "license": "CC BY 4.0 — Statistics Norway (SSB)",
        "attribution": "Statistics Norway (SSB), data.ssb.no",
        "fetch_date": datetime.date.today().isoformat(),
        "age_range": "18-95",
        "sex_codes": "1=Menn, 2=Kvinner",
        "klass_overlap_pct": f"{overlap_pct:.1f}",
        "notes": (
            "Live-fetched from SSB PxWeb API v0. "
            "Age codes 018-095 (0-padded 3-digit SSB codes decoded to int). "
            "Only KLASS-131 terminal-2024 municipality codes (4-digit) included. "
            "omsorgsradar cache (data/cache/07459.json) covers ages 80-104 only "
            "and was not used for this snapshot."
        ),
    }

    import pyarrow as pa
    import pyarrow.parquet as pq

    table = pa.Table.from_pandas(df, preserve_index=False)
    table = table.replace_schema_metadata(
        {k: v for k, v in metadata.items()}
    )

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, OUTPUT_PATH, compression="snappy")

    size_mb = OUTPUT_PATH.stat().st_size / 1_048_576
    print(
        f"Wrote {OUTPUT_PATH} ({size_mb:.2f} MB, {total_rows:,} rows)",
        file=sys.stderr,
    )
    if size_mb > 2.0:
        print(
            f"WARNING: snapshot is {size_mb:.2f} MB > 2 MB target. "
            "Consider reducing age range or using gzip compression.",
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
