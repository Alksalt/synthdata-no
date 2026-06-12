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
