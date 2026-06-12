# AGENTS.md — synthdata-no build phases

Same brief as `CLAUDE.md`, for codex/fresh instances. Phases run only after the owner's explicit go.
Model policy (`../CLAUDE.md`): **Opus** plans/reviews/designs fnr+gold-span logic; **Sonnet** implements
and fans out; **never Haiku**.

- **P0 — Persons + fnr core.** `uv` project scaffold; vendor the mod-11 checksum from omsorgsradar (attrib);
  fnr/D-nummer builder applying the +80 month (and +40 day for D-numbers) Tenor offset; Faker `nb_NO`
  persons; SSB KLASS kommune fetch + cache. *Tests:* month ∈ 81–92 for all generated fnr; checksum
  validates; no generated value is a valid real fnr; same seed → identical output; D-number stacks both
  offsets.
- **P1 — Tabular sets.** Config-driven row-level frames (`kommune`/`age`/`sex`/`diagnosis_group`/
  `service_use`) with configurable marginals + deterministic seeds; optional embedded synthetic PII column
  for the anonymize demo. *Tests:* seed-reproducibility; marginals match the requested config within
  tolerance; kommune values are all KLASS-valid.
- **P2 — Clinical text.** Templated bokmål snippets with negation/uncertainty cues + section headers, each
  carrying gold spans (negated/uncertain token spans, section labels). *Tests:* every snippet's gold spans
  are internally consistent; cue inventory covers the `medspacy-no` ConText categories; seed-reproducible.
- **P3 — FHIR R4 bundles.** `Patient`/`MedicationStatement`/`MedicationRequest`/`Condition`/`Observation`
  → transaction `Bundle`s; synthetic person identifiers flow into `Patient.identifier`; coded fields from a
  curated, license-clean ATC/ICD-10 subset (config, never inline). *Tests:* bundles validate against R4
  structure; identifiers are synthetic-range; codes resolve to the curated set.
- **P4 — Integration fixtures + publish.** Ready-made fixture exports tailored to each consumer
  (`medspacy-no` snippet packs, `fhir-safety-harness` bundles, `omsorgsradar` Norwegian tabular fixture
  replacing the US-BRFSS one); README (EN + bokmål summary), LICENSE; PyPI release. *Tests:* each consumer's
  fixture loads and matches its expected schema; a smoke test per consumer.
