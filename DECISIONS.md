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
