"""synthdata-no CLI — deterministic generator of synthetic Norwegian health data.

Entry point: ``synthdata-no``

Subcommands:
    persons     Generate synthetic persons (CSV or JSON)
    table       Generate a synthetic tabular dataset (CSV)
    text        Generate synthetic bokmål clinical text (JSONL)
    fhir        Generate FHIR R4B patient bundles (JSON directory)
    fixtures    Emit all three consumer fixture sets

Common flags:
    --seed INT   RNG seed (default: 42)
    --n INT      Number of records (default: 10)
    --out PATH   Output path or directory

All subcommands are deterministic: same --seed + --n → byte-identical output.
No real persons are generated. NOT for statistical inference.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import click

# Lazy imports to keep startup fast; each subcommand imports only what it needs.


@click.group()
@click.version_option(package_name="synthdata-no")
def cli() -> None:
    """synthdata-no — synthetic Norwegian health data generator.

    No real persons. No re-identification risk by construction.
    NOT for statistical inference about the Norwegian population.
    """


# ---------------------------------------------------------------------------
# persons subcommand
# ---------------------------------------------------------------------------

@cli.command("persons")
@click.option("--seed", default=42, show_default=True, help="RNG seed.")
@click.option("--n", default=10, show_default=True, help="Number of persons to generate.")
@click.option(
    "--out",
    required=True,
    type=click.Path(),
    help="Output CSV path (e.g. persons.csv).",
)
@click.option("--dnr", is_flag=True, default=False, help="Generate D-numbers instead of fnr.")
def persons_cmd(seed: int, n: int, out: str, dnr: bool) -> None:
    """Generate synthetic Norwegian persons.

    Output is a CSV with columns: name, fnr, birth_date, sex, address, postal_code, kommune.
    All identifiers are in the Tenor synthetic range (month 81–92).
    """
    from synthdata_no.persons import generate_persons
    import pandas as pd

    records = generate_persons(n, seed, dnr=dnr)
    rows = [
        {
            "name": p.name,
            "fnr": p.fnr,
            "birth_date": p.birth_date.isoformat(),
            "sex": p.sex,
            "address": p.address,
            "postal_code": p.postal_code,
            "kommune": p.kommune,
        }
        for p in records
    ]
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(out_path, index=False)
    click.echo(f"Wrote {n} persons → {out_path}")


# ---------------------------------------------------------------------------
# table subcommand
# ---------------------------------------------------------------------------

@cli.command("table")
@click.option("--seed", default=42, show_default=True, help="RNG seed.")
@click.option("--n", default=10, show_default=True, help="Number of rows to generate.")
@click.option(
    "--out",
    required=True,
    type=click.Path(),
    help="Output CSV path (e.g. table.csv).",
)
def table_cmd(seed: int, n: int, out: str) -> None:
    """Generate a synthetic tabular dataset with Norwegian kommune marginals.

    Output is a CSV with columns: kommune, age, sex, tjeneste_bruk, diagnosekategori.
    Uses SSB 07459 marginals. NOT for statistical inference.
    """
    from synthdata_no.tabular import generate_table

    df = generate_table({}, n=n, seed=seed)
    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(out_path, index=False)
    click.echo(f"Wrote {n} rows → {out_path}")


# ---------------------------------------------------------------------------
# text subcommand
# ---------------------------------------------------------------------------

@cli.command("text")
@click.option("--seed", default=42, show_default=True, help="RNG seed.")
@click.option("--n", default=10, show_default=True, help="Number of records to generate.")
@click.option(
    "--out",
    required=True,
    type=click.Path(),
    help="Output JSONL path (e.g. clinical.jsonl).",
)
def text_cmd(seed: int, n: int, out: str) -> None:
    """Generate synthetic bokmål clinical text with gold ConText annotations.

    Output is JSONL (one record per line) with char-offset entity spans.
    Covers negation, possibility, historical, family, and hypothetical contexts.
    """
    from synthdata_no.export.medspacy import to_jsonl

    out_path = Path(out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    to_jsonl(out_path, n=n, seed=seed)
    click.echo(f"Wrote {n} records → {out_path}")


# ---------------------------------------------------------------------------
# fhir subcommand
# ---------------------------------------------------------------------------

@cli.command("fhir")
@click.option("--seed", default=42, show_default=True, help="RNG seed.")
@click.option("--n", default=10, show_default=True, help="Number of patient bundles.")
@click.option(
    "--out",
    required=True,
    type=click.Path(),
    help="Output directory for patient JSON bundles + index.json.",
)
def fhir_cmd(seed: int, n: int, out: str) -> None:
    """Generate FHIR R4B patient bundles (transaction type).

    Output directory contains one patient_NNNN.json per patient plus index.json.
    All identifiers are in the Tenor synthetic range. Offline validation only —
    full no-basis profile validation is a release-gate step for consumers.
    """
    from synthdata_no.export.safety_harness import write_fixture_set

    out_path = Path(out)
    write_fixture_set(out_path, n_patients=n, seed=seed)
    click.echo(f"Wrote {n} FHIR bundles + index.json → {out_path}")


# ---------------------------------------------------------------------------
# fixtures subcommand
# ---------------------------------------------------------------------------

@cli.command("fixtures")
@click.option("--seed", default=42, show_default=True, help="RNG seed.")
@click.option("--n", default=10, show_default=True, help="Records per consumer fixture set.")
@click.option(
    "--n-fhir",
    "n_fhir",
    default=None,
    type=int,
    show_default=True,
    help=(
        "Number of FHIR patient bundles to emit. "
        "Defaults to min(--n, 20) to avoid flooding large fixture runs. "
        "Pass explicitly to override (e.g. --n-fhir 50)."
    ),
)
@click.option(
    "--out",
    required=True,
    type=click.Path(),
    help="Output root directory. Sub-dirs: omsorgsradar/, medspacy_no/, fhir_safety_harness/.",
)
def fixtures_cmd(seed: int, n: int, n_fhir: int | None, out: str) -> None:
    """Emit all three consumer fixture sets.

    Layout::

        <out>/
          omsorgsradar/        brfss-shaped CSV (state, age, sex, diabetes, notes)
          medspacy_no/         clinical.jsonl   gold-annotated bokmål text
          fhir_safety_harness/ patient bundles  JSON + index.json

    Each fixture set is deterministic. seed=42, n=10 produces the default demo set.
    For the omsorgsradar fixture the canonical n is 600 rows (seed 42); here we honour
    the --n flag but note that the brfss-demo pipeline expects ≥600 rows for k=10 analysis.

    FHIR bundles are capped at min(--n, 20) by default — each bundle is a full JSON file
    and large n floods the output directory. Use --n-fhir to override.
    """
    from synthdata_no.export.omsorgsradar import write_brfss_shaped_fixture
    from synthdata_no.export.medspacy import to_jsonl
    from synthdata_no.export.safety_harness import write_fixture_set

    root = Path(out)
    effective_n_fhir = n_fhir if n_fhir is not None else min(n, 20)

    # omsorgsradar
    omsr_dir = root / "omsorgsradar"
    omsr_dir.mkdir(parents=True, exist_ok=True)
    write_brfss_shaped_fixture(omsr_dir / "brfss_sample.csv", seed=seed)
    click.echo(f"omsorgsradar fixture → {omsr_dir / 'brfss_sample.csv'}")

    # medspacy-no
    med_dir = root / "medspacy_no"
    med_dir.mkdir(parents=True, exist_ok=True)
    to_jsonl(med_dir / "clinical.jsonl", n=max(n, 50), seed=seed)
    click.echo(f"medspacy_no fixture → {med_dir / 'clinical.jsonl'}")

    # fhir-safety-harness
    fhir_dir = root / "fhir_safety_harness"
    write_fixture_set(fhir_dir, n_patients=effective_n_fhir, seed=seed)
    click.echo(f"fhir_safety_harness fixture → {fhir_dir} ({effective_n_fhir} bundles)")

    click.echo(f"\nAll fixtures written to {root}")
