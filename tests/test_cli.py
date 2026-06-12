"""CLI smoke tests — R1.

Each subcommand runs via click's test runner (equivalent to `uv run synthdata-no … --seed 1 --n 5 --out tmp`).
Tests:
  - Each subcommand exits 0 and produces expected files.
  - Determinism: persons subcommand output is identical across two invocations with same seed.
  - --version works.
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest
from click.testing import CliRunner

from synthdata_no.cli import cli


@pytest.fixture()
def runner() -> CliRunner:
    return CliRunner()


# ---------------------------------------------------------------------------
# --version
# ---------------------------------------------------------------------------

def test_version(runner: CliRunner) -> None:
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0, result.output
    assert "0.1.0" in result.output


# ---------------------------------------------------------------------------
# persons subcommand
# ---------------------------------------------------------------------------

def test_persons_runs(runner: CliRunner, tmp_path: Path) -> None:
    out = str(tmp_path / "persons.csv")
    result = runner.invoke(cli, ["persons", "--seed", "1", "--n", "5", "--out", out])
    assert result.exit_code == 0, result.output
    assert Path(out).exists()
    df = pd.read_csv(out)
    assert len(df) == 5
    expected_cols = {"name", "fnr", "birth_date", "sex", "address", "postal_code", "kommune"}
    assert expected_cols <= set(df.columns)


def test_persons_fnr_tenor_range(runner: CliRunner, tmp_path: Path) -> None:
    """All generated fnr must have month in 81–92 (Tenor range)."""
    out = str(tmp_path / "persons.csv")
    runner.invoke(cli, ["persons", "--seed", "1", "--n", "20", "--out", out])
    df = pd.read_csv(out, dtype={"fnr": str})
    for fnr in df["fnr"]:
        fnr = fnr.zfill(11)
        month = int(fnr[2:4])
        assert month >= 81, f"fnr {fnr!r} has month {month} — not in Tenor range"


def test_persons_determinism(runner: CliRunner, tmp_path: Path) -> None:
    out1 = str(tmp_path / "p1.csv")
    out2 = str(tmp_path / "p2.csv")
    runner.invoke(cli, ["persons", "--seed", "42", "--n", "5", "--out", out1])
    runner.invoke(cli, ["persons", "--seed", "42", "--n", "5", "--out", out2])
    assert Path(out1).read_text() == Path(out2).read_text()


def test_persons_different_seeds_differ(runner: CliRunner, tmp_path: Path) -> None:
    out1 = str(tmp_path / "p1.csv")
    out2 = str(tmp_path / "p2.csv")
    runner.invoke(cli, ["persons", "--seed", "1", "--n", "5", "--out", out1])
    runner.invoke(cli, ["persons", "--seed", "2", "--n", "5", "--out", out2])
    assert Path(out1).read_text() != Path(out2).read_text()


# ---------------------------------------------------------------------------
# table subcommand
# ---------------------------------------------------------------------------

def test_table_runs(runner: CliRunner, tmp_path: Path) -> None:
    out = str(tmp_path / "table.csv")
    result = runner.invoke(cli, ["table", "--seed", "1", "--n", "5", "--out", out])
    assert result.exit_code == 0, result.output
    assert Path(out).exists()
    df = pd.read_csv(out)
    assert len(df) == 5
    expected_cols = {"kommune", "age", "sex"}
    assert expected_cols <= set(df.columns)


def test_table_kommune_valid(runner: CliRunner, tmp_path: Path) -> None:
    """All kommune codes must be valid 4-digit KLASS codes."""
    from synthdata_no.kommuner import valid_kommune_codes
    out = str(tmp_path / "table.csv")
    runner.invoke(cli, ["table", "--seed", "1", "--n", "20", "--out", out])
    df = pd.read_csv(out, dtype={"kommune": str})
    valid = set(valid_kommune_codes())
    for k in df["kommune"]:
        assert k in valid, f"kommune {k!r} not in KLASS snapshot"


# ---------------------------------------------------------------------------
# text subcommand
# ---------------------------------------------------------------------------

def test_text_runs(runner: CliRunner, tmp_path: Path) -> None:
    out = str(tmp_path / "clinical.jsonl")
    result = runner.invoke(cli, ["text", "--seed", "1", "--n", "5", "--out", out])
    assert result.exit_code == 0, result.output
    assert Path(out).exists()
    lines = [json.loads(l) for l in Path(out).read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(lines) == 5
    for rec in lines:
        assert "text" in rec
        assert "spans" in rec
        assert "meta" in rec


def test_text_has_gold_context(runner: CliRunner, tmp_path: Path) -> None:
    out = str(tmp_path / "clinical.jsonl")
    runner.invoke(cli, ["text", "--seed", "1", "--n", "20", "--out", out])
    lines = [json.loads(l) for l in Path(out).read_text(encoding="utf-8").splitlines() if l.strip()]
    gold_contexts = {rec["meta"]["gold_context"] for rec in lines}
    # Should cover at least several categories in 20 records
    valid = {"NEGATED_EXISTENCE", "POSSIBLE_EXISTENCE", "HYPOTHETICAL", "HISTORICAL", "FAMILY", "AFFIRMED"}
    assert gold_contexts <= valid
    assert len(gold_contexts) >= 2


# ---------------------------------------------------------------------------
# fhir subcommand
# ---------------------------------------------------------------------------

def test_fhir_runs(runner: CliRunner, tmp_path: Path) -> None:
    out = str(tmp_path / "fhir_out")
    result = runner.invoke(cli, ["fhir", "--seed", "1", "--n", "3", "--out", out])
    assert result.exit_code == 0, result.output
    out_dir = Path(out)
    assert (out_dir / "index.json").exists()
    assert (out_dir / "patient_0000.json").exists()
    assert (out_dir / "patient_0002.json").exists()
    index = json.loads((out_dir / "index.json").read_text())
    assert index["n_patients"] == 3
    assert index["seed"] == 1


def test_fhir_bundles_have_patient(runner: CliRunner, tmp_path: Path) -> None:
    out = str(tmp_path / "fhir_out")
    runner.invoke(cli, ["fhir", "--seed", "1", "--n", "2", "--out", out])
    for i in range(2):
        bundle = json.loads((Path(out) / f"patient_{i:04d}.json").read_text())
        resource_types = [e["resource"]["resourceType"] for e in bundle["entry"]]
        assert "Patient" in resource_types


# ---------------------------------------------------------------------------
# fixtures subcommand
# ---------------------------------------------------------------------------

def test_fixtures_runs(runner: CliRunner, tmp_path: Path) -> None:
    out = str(tmp_path / "fixtures_out")
    result = runner.invoke(cli, ["fixtures", "--seed", "1", "--n", "5", "--out", out])
    assert result.exit_code == 0, result.output
    root = Path(out)
    # omsorgsradar
    assert (root / "omsorgsradar" / "brfss_sample.csv").exists()
    # medspacy_no
    assert (root / "medspacy_no" / "clinical.jsonl").exists()
    # fhir_safety_harness
    assert (root / "fhir_safety_harness" / "index.json").exists()


def test_fixtures_omsorgsradar_schema(runner: CliRunner, tmp_path: Path) -> None:
    """brfss_sample.csv must have the exact brfss-demo contract columns."""
    out = str(tmp_path / "fixtures_out")
    runner.invoke(cli, ["fixtures", "--seed", "42", "--n", "5", "--out", out])
    df = pd.read_csv(
        Path(out) / "omsorgsradar" / "brfss_sample.csv",
        dtype={"state": str},
    )
    assert list(df.columns) == ["state", "age", "sex", "diabetes", "notes"]
    assert len(df) == 600  # write_brfss_shaped_fixture always emits 600 rows


def test_fixtures_fhir_cap_default(runner: CliRunner, tmp_path: Path) -> None:
    """FHIR bundles are capped at min(n, 20) by default — no --n-fhir given."""
    out = str(tmp_path / "fixtures_cap")
    result = runner.invoke(cli, ["fixtures", "--seed", "1", "--n", "5", "--out", out])
    assert result.exit_code == 0, result.output
    fhir_dir = Path(out) / "fhir_safety_harness"
    index = json.loads((fhir_dir / "index.json").read_text())
    # n=5, cap=min(5,20)=5
    assert index["n_patients"] == 5


def test_fixtures_fhir_cap_large_n(runner: CliRunner, tmp_path: Path) -> None:
    """With --n 30, FHIR defaults to 20 bundles (min(30, 20))."""
    out = str(tmp_path / "fixtures_cap_large")
    result = runner.invoke(cli, ["fixtures", "--seed", "1", "--n", "30", "--out", out])
    assert result.exit_code == 0, result.output
    fhir_dir = Path(out) / "fhir_safety_harness"
    index = json.loads((fhir_dir / "index.json").read_text())
    assert index["n_patients"] == 20


def test_fixtures_fhir_n_fhir_override(runner: CliRunner, tmp_path: Path) -> None:
    """--n-fhir overrides the default cap."""
    out = str(tmp_path / "fixtures_override")
    result = runner.invoke(
        cli, ["fixtures", "--seed", "1", "--n", "30", "--n-fhir", "3", "--out", out]
    )
    assert result.exit_code == 0, result.output
    fhir_dir = Path(out) / "fhir_safety_harness"
    index = json.loads((fhir_dir / "index.json").read_text())
    assert index["n_patients"] == 3
