# synthdata-no — concept (scaffolded 2026-06-12)

A deterministic, seedable generator of fake Norwegian health-adjacent data. Built to be the shared
test-data substrate for `medspacy-no`, `fhir-safety-harness`, and `omsorgsradar` (see `CLAUDE.md`).
Prior art it stands on, not ahead of: **Skatteetaten Tenor / Test-Norge** (synthetic folkeregister) for
the person layer, and **Synthea** internationally for synthetic clinical records. No first-mover claims.

## Generator families

1. **Synthetic persons.** Faker `nb_NO` for names/addresses + a fødselsnummer/D-nummer builder that emits
   only **synthetic-range** identifiers with valid mod-11 control digits (see convention below). Fields:
   name, fnr/d-nummer, birth date, sex (derived from the individnummer parity rule), address, kommune.
2. **Bokmål clinical free-text snippets.** Templated sentences carrying the linguistic phenomena
   `medspacy-no` must detect: negation (`ikke`, `ingen tegn til`, `uten`, `negativ for`), uncertainty
   (`kan ikke utelukkes`, `mistanke om`, `mulig`, `sannsynlig`), and section headers
   (`Aktuelt:`, `Vurdering:`, `Tiltak:`, `Sykehistorie:`). Each snippet ships with gold spans (which token
   span is negated/uncertain, which section it sits under) so ConText rules can be scored. Templated only —
   no LLM generation in the core path (deterministic, reviewable by the owner).
3. **FHIR R4 resources.** `Patient`, `MedicationStatement`, `MedicationRequest`, `Condition`,
   `Observation`, assembled into transaction `Bundle`s. Synthetic identifiers in the person layer flow into
   `Patient.identifier`. Coded fields use real code systems (ATC, ICD-10, SNOMED slices) but only on a
   curated, license-clean subset; codes are config-driven, never hand-typed inline.
4. **Tabular row-level datasets.** Health-adjacent frames: `kommune`, `age`, `sex`, `diagnosis_group`,
   `service_use`, with **configurable marginal distributions** and **deterministic seeds**. This is the
   Norwegian replacement for omsorgsradar's US-BRFSS-shaped anonymize-stage fixture — same role
   (row-level data with embeddable PII for the k-anonymity / residual-risk demo), Norwegian shape.

## Synthetic fødselsnummer — HARD convention (verified)

Norway's official synthetic population test data (**Skatteetaten Tenor / syntetisk folkeregister**) marks a
number as synthetic by **adding 80 to the month field** (`MM → MM+80`), for both fødselsnummer and
D-numbers, with the mod-11 control digits computed **after** the offset. A person "born" 01.11.2024 gets
birth-date digits `019124` (month `11 → 91`). Real months are 01–12, so synthetic months land in **81–92**
and can never collide with a real fnr.

D-numbers independently add **40 to the day** field (`DD → DD+40`, the standard D-number marker). A
**synthetic D-number therefore stacks both offsets**: day `+40` AND month `+80`.

**Constraint adopted:** every generated identifier MUST use the synthetic month range (81–92). The
generator builds the date stem with the offset, then appends control digits via the vendored mod-11
logic. Tests assert: (a) month ∈ 81–92 for every generated fnr; (b) checksum validates; (c) no generated
value is a valid *real* (un-offset) fnr.

**Vendored checksum.** The mod-11 logic is vendored from omsorgsradar:
`/Users/ol/agents/ehelse_project/omsorgsradar/src/omsorgsradar/core/anonymize/pii.py`
(`valid_fnr_checksum`, `append_fnr_control_digits`, weights `_FNR_K1_W` / `_FNR_K2_W`). Copy with attribution;
do not re-derive. The generator wraps `append_fnr_control_digits` after applying the +80 (and, for
D-numbers, +40) offset to the date stem.

## Kommune codes
Kommune codes come from the **SSB KLASS API** (`klass.ssb.no`, classification 131) — fetched and cached,
**never a hand-written list** (workspace constraint, mirrors omsorgsradar). Merger history is out of scope
for v0.1; a fixed snapshot of valid kommunenummer is enough for test fixtures.

## Rejected alternatives
- **Full Synthea-Norway port** — too heavy: Synthea's disease-progression engine and module DSL are a
  multi-month port for realism this project does not need. We generate templated/structured fakes targeted
  at the three consumers' test needs, not a longitudinal-record simulator.
- **SDV / CTGAN / trained synthesizers** — these learn from real data; by design we have none (REK-gated).
  A learned generator would need real training microdata, which is the exact barrier this project exists to
  route around. Out of scope until/unless real data is ever lawfully available.
- **LLM-generated clinical text as the core path** — non-deterministic and unreviewable at scale. Templates
  with gold spans stay deterministic and let the owner (utdannet lege) sign off on realism. An optional LLM
  augmentation layer can come later, off the default seed-reproducible path.

## Deliverables sketch (the future build's call on details)
`uv`-based Python package · deterministic seeds threaded everywhere (one seed → byte-identical output) ·
per-family generator modules + a thin CLI · pytest with known-value tests · ready-made fixture exports for
the three consumer projects · PyPI eventually. Packaging/versioning decisions belong to the build, not this
scaffold.

## Sources
- [Tenor testdata — Skatteetaten](https://www.skatteetaten.no/en/testdata/)
- [Ny versjon av syntetisk folkeregister — Skatteetaten (folkeregisteret-api-dokumentasjon)](https://skatteetaten.github.io/folkeregisteret-api-dokumentasjon/ny-versjon-av-syntetisk-folkeregister/)
- [testnorge-tenor-adapter — Skatteetaten (GitHub)](https://github.com/Skatteetaten/testnorge-tenor-adapter)
