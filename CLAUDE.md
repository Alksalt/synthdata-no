# CLAUDE.md — synthdata-no (Syntetiske norske helsedata)

**Synthetic Norwegian health-data generator.** A `uv`-based Python package that emits four families of
realistic-but-fake data: (1) synthetic persons (Faker `nb_NO` + valid-checksum, synthetic-range
fødselsnummer/D-nummer), (2) templated bokmål clinical free-text snippets with negation/uncertainty cues
and section structure, (3) FHIR R4 resources/bundles, (4) row-level tabular health-adjacent datasets with
configurable distributions and deterministic seeds.

## Why this project exists
- **On-thesis substrate.** Every project in this portfolio is blocked from real Norwegian patient data —
  REK approval is ~1.5y out (`../CLAUDE.md`). A shared synthetic-data layer is the ethics-free way to test
  and demo all of them. The owner's clinical credential (rule authoring, gold-labeling, realism review)
  substitutes for data access.
- **Shared test-data layer for three siblings:**
  - `medspacy-no/` — synthetic bokmål clinical snippets (negation/uncertainty/section structure) to test
    ConText rules without touching real journals.
  - `fhir-safety-harness/` — synthetic FHIR R4 `Patient`/`MedicationStatement`/`MedicationRequest` bundles
    as substrate for safety traps.
  - `omsorgsradar/` — synthetic row-level tabular sets (kommune/age/sex/diagnosis-group/service-use) for
    the anonymize-stage demo, replacing the current US-BRFSS-shaped fixture with a Norwegian one.

## Files
- Concept + generator families + verified conventions + rejected alternatives: `docs/CONCEPT.md`
- Hard constraints: `DECISIONS.md` · Build phases: `AGENTS.md` · Live state: `status.md`

## Workspace rules apply (`../CLAUDE.md`)
Markdown scaffold until the owner explicitly starts the build · Python via `uv` only · owner is
«utdannet lege (master i medisin)», never bare «lege» · no real patient data, ever · no absolute
first-mover claims («…that we are aware of» only) · never «ikke-kommersiell» framing.

Status: **scaffolded 2026-06-12 — build not started.**
