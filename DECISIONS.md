# Decisions — synthdata-no

Hard constraints. Workspace-wide rules in `../CLAUDE.md` apply on top.

- Synthetic data only — never real patient data, never real persons, ever.
- Every generated fødselsnummer/D-nummer MUST sit in the Tenor synthetic range: month +80 (so month ∈
  81–92), D-numbers additionally day +40; mod-11 control digits computed AFTER the offsets. No generated
  value may be a valid real (un-offset) fnr.
- Vendor the mod-11 checksum from omsorgsradar
  (`/Users/ol/agents/ehelse_project/omsorgsradar/src/omsorgsradar/core/anonymize/pii.py` —
  `valid_fnr_checksum`, `append_fnr_control_digits`, `_FNR_K1_W`, `_FNR_K2_W`), with attribution. Do not
  re-derive the algorithm.
- Deterministic seeds mandatory across every generator family: one seed → byte-identical output. No
  un-seeded randomness on the default path.
- Kommune codes come from the SSB KLASS API (`klass.ssb.no`, classification 131) — never a hand-written
  list.
- Clinical-text core path is templated + gold-spanned, deterministic. LLM generation, if ever added, is an
  opt-in augmentation layer off the default reproducible path.
- Python via `uv` only. Markdown scaffold until the owner explicitly starts the build.
- No absolute first-mover claims — cite Tenor (persons) and Synthea (clinical) as prior art; «…that we are
  aware of» phrasing only.
- Never «ikke-kommersiell» / «non-commercial» framing.
- Owner is «utdannet lege (master i medisin)» in any outward text — never bare «lege».
- FHIR target: **R4B** via `fhir.resources.R4B` sub-package (pydantic v2, BSD, maintained). R4 sub-package dropped at fhir-resources v7 — never use the R4 sub-package.
- Clinical text gold format: **Prodigy-style JSONL** (char-offset spans + `meta.gold_context` + `template_id`); `to_spacy_examples()` adapter. No DocBin in the distribution — consumers convert.
- ICD-10: code-only embedded. No Norwegian display names (adaptation under WHO CC BY-ND 3.0 IGO — uncleared). User-supplied display files are supported.
- Code-system SHIP/AVOID: ATC+varenavn via FEST (SHIP, NLOD 2.0), LOINC handful (SHIP, Regenstrief attribution notice), ICD-10 codes-only (grey-SHIP), ATC via WHOCC directly (AVOID), ICPC-2 (AVOID), SNOMED CT (AVOID), NLK/NPU (AVOID embed).
- Package name: **synthdata-no** (PyPI); import name: `synthdata_no`.
- `Faker('no_NO').ssn()` is permanently banned — emits real-range fnr. Use `synthetic_fnr()` / `synthetic_dnr()` from `ids.py` exclusively.
