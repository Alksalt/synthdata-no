# status — synthdata-no

- **2026-06-12** — v0.1 built: 227 tests green (193 original + 13 CLI + 21 consumer smoke).
  CLI `synthdata-no persons|table|text|fhir|fixtures` entry point wired.
  README + PHYSICIAN_REVIEW.md written. Consumer smoke tests for omsorgsradar, medspacy-no, fhir-safety-harness pass.
  `uv build` clean. GitHub repo Alksalt/synthdata-no created + pushed.
  **PyPI = owner gate** — artifacts ready, publication not done.
- **2026-06-12** — Review panel close-out: correctness PASS (Tenor-pair checksums hand-recomputed,
  century round-trips verified), security/licensing PASS (real-range-fnr invariant held under
  adversarial probing; SHIP/AVOID licensing table compliant; **PyPI publish cleared from
  security/licensing standpoint**), integration BLOCK overturned (its missing-tests/CI/scripts
  findings were a reviewer-environment artifact — all files git-tracked, wheel verified working in
  an isolated venv). Fixes applied: global `random.seed` removed (isolation hazard), annotation fix,
  `requests` → dev group. 227 tests, CI green. **Owner gates: `uv publish` + PHYSICIAN_REVIEW.md.**
- **2026-06-12** — **Six-agent review (3 blind) → fix round → domain re-check PASS.** Blind domain
  + silent-failure BLOCKs fixed same day: per-patient FHIR variety (meds/conditions/kreatinin),
  kjønnskorrekte navn uten titler, 8 template-reparasjoner, CPT-vakter (sex-key/age-band/planted-
  count → ValueError), century-grenser per Skatteetaten-spec (1854; 900–999 = kun 1940–1999),
  Faker låst <26 + «Determinism scope»-note, spacy som `[nlp]`-extra, /Users/-stier skrubbet,
  `top_n_kommuner=12` (anonymize-demo overlever k=10 utenfor Oslo), CI-badge. Tester 227 → **261**
  (+ env-gated cross-repo smoke 21/21). Kjent rest (ikke-blokkerende): filler-pool blander
  symptomer inn i behandlings-slots — se review-md; hører til PHYSICIAN_REVIEW-passet.
  **PyPI-gate ligger nå kun hos eier.**
