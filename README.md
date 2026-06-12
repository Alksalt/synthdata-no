# synthdata-no

**Deterministic generator of synthetic Norwegian health data.**

Combines Tenor-range synthetic fødselsnummer, gold-annotated bokmål clinical text, no-basis-aware FHIR R4B bundles, and tabular microdata with Norwegian kommune marginals — all in one pip-installable package.

Produced as a shared synthetic substrate for the open Norwegian health-AI portfolio:
[medspacy-no](https://github.com/Alksalt/medspacy-no) · [fhir-safety-harness](https://github.com/Alksalt/fhir-safety-harness) · [omsorgsradar](https://github.com/Alksalt/omsorgsradar)

No real persons. No re-identification risk by construction. NOT for statistical inference about the Norwegian population.

---

## Installation

```bash
pip install synthdata-no          # PyPI (owner gate — not yet published)
# or from source:
git clone https://github.com/Alksalt/synthdata-no
cd synthdata-no
uv sync
uv run synthdata-no --help
```

---

## Four data families

### 1. Persons — Tenor-range synthetic identifiers

Generates `Person` records with fødselsnummer or D-nummer in the [Tenor/Test-Norge](https://www.tenor.no) synthetic range (month+80, mod-11 checksum computed after the offset). Backed by Faker `no_NO` for names/addresses and the SSB KLASS 131 kommune registry.

**CLI:**

```bash
uv run synthdata-no persons --seed 42 --n 100 --out persons.csv
```

**Python:**

```python
from synthdata_no.persons import generate_persons

persons = generate_persons(n=100, seed=42)
for p in persons[:3]:
    print(p.name, p.fnr, p.kommune)
```

Synthetic fnr convention: month digits are offset by 80 (month ∈ 81–92); D-nr additionally offset by 40 in the day digits. Example: a person born 17 November 2020 gets fnr `17912099997` and D-nr `57912075186` (verified Tenor pair). No generated identifier has month ≤ 12 — a guard test enforces this.


### 2. Tabular — Norwegian kommune microdata

Generates a synthetic microdata table driven by SSB 07459 population marginals (age × sex × kommune). Correlated columns via configurable conditional probability tables (CPTs). Optional planted Tenor-range fnr for anonymization pipeline testing.

**CLI:**

```bash
uv run synthdata-no table --seed 42 --n 600 --out table.csv
```

**Python:**

```python
from synthdata_no.tabular import generate_table

df = generate_table({}, n=600, seed=42)
print(df.head())
```

Default columns: `kommune` (4-digit KLASS code), `age`, `sex`, `tjeneste_bruk`, `diagnosekategori`.


### 3. Clinical text — gold-annotated bokmål snippets

Generates synthetic bokmål clinical text records with character-offset entity spans compatible with [medspacy-no](https://github.com/Alksalt/medspacy-no). Covers all six ConText categories: NEGATED_EXISTENCE, POSSIBLE_EXISTENCE, HYPOTHETICAL, HISTORICAL, FAMILY, AFFIRMED. Includes pseudo-negation traps (`kan ikke utelukkes` → POSSIBLE, not NEGATED), conjunction-scope traps, abbreviation-bearing sentences, and 15 section-header families.

**CLI:**

```bash
uv run synthdata-no text --seed 42 --n 500 --out clinical.jsonl
```

**Python:**

```python
from synthdata_no.export.medspacy import to_jsonl, to_spacy_examples
import spacy

path = to_jsonl("clinical.jsonl", n=500, seed=42)
nlp = spacy.blank("nb")
examples = to_spacy_examples(path, nlp)
print(examples[0].reference.ents)
```

JSONL shape: `{"text", "spans": [{start, end, label, token_start, token_end}], "meta": {gold_context, trigger, section, template_id}}`.


### 4. FHIR — no-basis-aware R4B bundles

Generates transaction Bundles (fhir.resources R4B) with Patient (no-basis-Patient profile), Medication (FEST+ATC dual coding), MedicationStatement, Condition (ICD-10-NO, code-only), and Observation (LOINC). All UUIDs are derived from the seeded RNG. Offline validation: pydantic model_validate round-trip + fhir-validator JSON-schema check.

**CLI:**

```bash
uv run synthdata-no fhir --seed 42 --n 5 --out fhir_out/
```

**Python:**

```python
from synthdata_no.export.safety_harness import write_fixture_set
from pathlib import Path

write_fixture_set(Path("fhir_out"), n_patients=5, seed=42)
# produces fhir_out/patient_0000.json … patient_0004.json + index.json
```

---

## Consumer quick-starts

### medspacy-no — ConText gold evaluation

```python
from synthdata_no.export.medspacy import to_jsonl, to_spacy_examples
import spacy

jsonl_path = to_jsonl("gold_eval.jsonl", n=500, seed=42)
nlp = spacy.blank("nb")
examples = to_spacy_examples(jsonl_path, nlp)
# examples is a list of spacy.training.Example with gold entity spans
```

### fhir-safety-harness — baseline fixture set

```python
from synthdata_no.export.safety_harness import write_fixture_set
from pathlib import Path

write_fixture_set(Path("fixtures/"), n_patients=5, seed=42)
# Each bundle is the no-trap baseline. Trap content is owner-authored in fhir-safety-harness.
```

### omsorgsradar — brfss-demo anonymize fixture

```python
from synthdata_no.export.omsorgsradar import write_brfss_shaped_fixture

df = write_brfss_shaped_fixture("analyses/brfss-demo/microdata/brfss_sample.csv", seed=42)
# 600 rows, columns: state (kommune code), age, sex, diabetes, notes
# notes[0] and notes[1] carry planted Tenor-range fnr for the anonymize pipeline
```

### All three at once

```bash
uv run synthdata-no fixtures --seed 42 --n 10 --out fixtures/
# fixtures/omsorgsradar/brfss_sample.csv
# fixtures/medspacy_no/clinical.jsonl
# fixtures/fhir_safety_harness/patient_0000.json … + index.json
```

---

## Honesty framing

> **Synthetic data statement:**
> All records generated by synthdata-no contain **no real persons**. Identifiers are constructed in the Tenor/Test-Norge synthetic range (month+80) and carry **no re-identification risk by construction** — they cannot be matched to any real register entry.
>
> This package is **NOT suitable for statistical inference** about the Norwegian population or Norwegian health services. Default marginals (SSB 07459) and CPT values are approximate aggregate-informed defaults, not calibrated epidemiological models.
>
> Clinical text templates were authored and reviewed by a physician (utdannet lege, master i medisin) for structural realism. No realism claim is made until the owner has completed the sign-off checklist in `PHYSICIAN_REVIEW.md`. The templates **do not represent typical Norwegian EPJ/journal text** — they are synthetic training examples for NLP evaluation.
>
> GDPR anonymity is not self-certified. For advice on whether this data is personal data in your context, consult Datatilsynet.

---

## Synthetic fnr convention

The Tenor Test-Norge marker is **month+80** applied before computing the mod-11 control digits:

| Real date | Real fnr (illustrative) | Synthetic fnr | Synthetic D-nr |
|-----------|------------------------|---------------|----------------|
| 17.11.2020 | 17112099nnn | 17**91**2099997 | **57**912075186 |

D-numbers additionally offset the day by +40. Both offsets are applied to the stem digits; the mod-11 control digits (k1, k2) are computed after the offsets. Values where k1=10 or k2=10 are discarded and regenerated (~17% of stems).

The `is_synthetic_fnr()` function returns True for any identifier in this range. The guard test in `tests/test_persons.py` asserts that no generated person ever has month ≤ 12.

---

## Prior art

The following prior art is acknowledged and cited:

- **Tenor / Test-Norge** (Skatteetaten/NAV): the official Norwegian synthetic ID register; synthdata-no uses the same marker convention (month+80) and is compatible with real Tenor-issued identifiers.
- **NorSynthClinical** (ltgoslo / University of Oslo): 477 manually-authored bokmål family-history sentences with entity/relation gold; does not cover ConText-style negation/context annotation — the gap this package addresses (to our knowledge).
- **Lund et al. 2024** (UNN-SPKI / Nor-DeID-SynthData): 1,200 GPT-4-generated Norwegian discharge summaries with PHI spans — a static de-identification benchmark, not a generator.
- **Synthea** (MITRE): active FHIR patient generator; `synthea-international/no/` is a renamed Finnish skeleton with no no-basis profile, no bokmål text, and US names. A full Norwegian port would require months of Java work.
- **fhir-kindling** (PyPI): closest pip-installable FHIR generator; profile-agnostic, no Norwegian layer.
- **NHN SyntPop** (Testuniverset): synthetic persons portal, HelseID-gated, demographics only, no FHIR/clinical content.

To our knowledge, no existing open pip-installable Python package combines Tenor-range identifiers, gold-annotated bokmål ConText text, and no-basis-aware FHIR R4B bundles in a single deterministic library.

---

## License and attribution

MIT License — see `LICENSE`.

Embedded data sources (see `THIRD_PARTY_SOURCES.md` for full attribution notices):

- **FEST** (DMP): NLOD 2.0. "Contains data from FEST (Forskrivnings- og ekspedisjonsstøtte), published by Direktoratet for medisinske produkter (DMP), made available under NLOD 2.0."
- **LOINC**: Regenstrief Institute. "This content includes LOINC codes … copyright © 1995 Regenstrief Institute, Inc. and the LOINC Committee … see https://loinc.org/license/."
- **ICD-10** (WHO): CC BY-ND 3.0 IGO — codes only, no Norwegian display names embedded (adaptation would require WHO permission).
- **SSB KLASS 131** (Statistics Norway): CC BY 4.0.

---

## Author

Oleksandr Altukhov — utdannet lege (master i medisin), agentic-AI engineer.

---

## Bokmål sammendrag

**synthdata-no** er et Python-bibliotek for deterministisk generering av syntetiske norske helsedata. Det produserer fire typer data:

1. **Fødselsnummer og D-nummer** i Tenor/Test-Norge-området (måned+80), med norske navn og adresser (Faker `no_NO`) og gyldige kommunekoder fra SSB KLASS 131.
2. **Tabelldata** med realistiske aldersfordelinger per kommune (SSB 07459), drevet av konfigurerbare betingede sannsynlighetstabeller.
3. **Klinisk tekst på bokmål** med gullmerkede entitetsspenn for ConText-evaluering — dekker negasjon, usikkerhet, historikk, familieanamnese og hypotetisk kontekst.
4. **FHIR R4B-bunter** med no-basis-Patient-profil, FEST+ATC-legemiddelkoding, ICD-10-NO-diagnoser (kun koder) og LOINC-observasjoner.

Biblioteket brukes som felles syntetisk grunnlag for [medspacy-no](https://github.com/Alksalt/medspacy-no), [fhir-safety-harness](https://github.com/Alksalt/fhir-safety-harness) og [omsorgsradar](https://github.com/Alksalt/omsorgsradar).

**Ingen reelle personer. Ingen gjenkjenningsrisiko. Ikke egnet for statistisk inferens om den norske befolkningen.**
