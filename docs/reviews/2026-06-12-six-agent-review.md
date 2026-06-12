# Six-agent independent review — 2026-06-12 (post-v0.1, pre-PyPI)

**Method:** 3 blind (no access to plans/status/DECISIONS; judged code + generated output + the
public GitHub clone cold) + 3 informed (deep statistics, real consumer-pipeline runs, silent-failure
hunt). **Verdicts:** blind-correctness PASS · blind-DX PASS · **blind-domain BLOCK** ·
informed-correctness PASS · informed-integration PASS · **silent-failure BLOCK**.

**One-liner:** the ID math, span offsets, licensing and packaging all hold; what fails is *realism
and edge-input honesty* — cloned FHIR patients, sex-mismatched names, a handful of ungrammatical
templates, and silent CPT fallbacks. All fixes are small; **PyPI stays gated until P0+P1 land.**

**Independently confirmed by this round (good news):** the omsorgsradar anonymize pipeline ran
END-TO-END on our fixture for the first time — verdict WARN (legit), verification 11/11, both
planted Tenor-range fnr caught and redacted, released CSV clean. medspacy JSONL: 500 records,
zero offset failures incl. æøå, trigger-direction sanity passed. FHIR set: all bundles validate,
FEST+ATC dual-coded, references resolve.

---

## P0 — blocks PyPI (realism/credibility)

**N1 · BLOCK (domain) · Every FHIR patient is clinically identical.**
`export/safety_harness.py:143-144` takes `atc_entries[:2]` / `icd10_entries[:2]` unconditionally +
hardcoded creatinine 85 — a 1995-born and a 1939-born patient get byte-identical clinical content;
the 51-drug catalog is never sampled. Fix: per-patient seeded sampling (1–3 meds, 1–3 conditions
via `rng.choice(..., replace=False)`), jittered creatinine (`rng.normal(85,18)` clipped 50–110).

**N2 · BLOCK (domain) · Person names uncorrelated with sex** — 21/40 mismatches («Astrid
Mikkelsen / M», «Sigurd Berntsen / F»); fnr↔sex is internally consistent, only the name is wrong.
Plus «Prof./Dr.» prefixes in patient names (I1). Fix: `persons.py` — `fake.name_male()` /
`fake.name_female()` branched on sex (also removes Faker title prefixes).

**N3 · BLOCK (domain) · Broken/ungrammatical templates with gold labels riding on them:**
«Pasienten har uten noen ødem…», «Medikamenter: Ingen utslett i bruk.» (drug-slot template fed a
symptom), «Pasienten ikke rapportert hoste.» (missing finite verb), «Ingen endokarditt klar
diagnose.», «Ikke vet vi sikkert om…» (archaic inversion), typo «Utiviklet» (I3). Fix: repair/
restrict those templates in `templates.toml` (filler-class constraints per template).

**N4 · CRITICAL (silent-failure) · CPT sex-key silent fallback.** `tabular.py:189` — a custom CPT
without `"1"`/`"2"` sex keys silently samples from the first band's first sex; output looks normal,
all tests pass, correlations are wrong. Fix: raise ValueError naming the band and valid keys.

## P1 — fix before PyPI (small)

- **N5 (2 agents):** `planted_fnr_count > n` → opaque IndexError (`tabular.py:220`); add the
  `ValueError` guard + test.
- **N6 (2 agents):** `fnr_birth_date` century gaps — individ 500–749 with yy 40–54 silently yields
  1840–1854 (never authorized); 900–999 missing the 2000–2039 branch per spec; lower bound 1855 vs
  spec 1854; zero round-trip coverage for 1855–1899. Latent (generator confined to 1930–2005) but a
  public-API landmine. Fix per blind-correctness finding 1 + tests spanning 1854/1899/1940/2000/2039.
- **N7:** `_age_band_label` silently clamps out-of-range ages to «65-95» (`tabular.py:46`); raise.
- **N8:** two tautological test assertions that can never fail (`tests/test_text.py:103` `or x==x`,
  `:144` `or True`); fix both.
- **N9:** Faker version pin `>=25.0` unbounded — name lists change between minors, so cross-install
  byte-determinism is NOT guaranteed; pin `faker>=25.0,<26` AND document that only Faker text
  fields are version-sensitive (structural determinism — fnr/codes/CPT — always holds).
- **N10 (DX):** `/Users/ol/agents/…` author paths in public source: `ids.py:9` docstring,
  `atc_fest.json` curation_note, `tests/test_consumer_smoke.py:66` (env-var it), DECISIONS/CONCEPT
  prose. Scrub/relativize.
- **N11 (DX):** README medspacy snippet `import spacy` fails for bare pip installs — add
  `[project.optional-dependencies] nlp = ["spacy>=3.8"]` + show `pip install "synthdata-no[nlp]"`.
- **N12 (integration):** brfss-shaped fixture at n=600 spreads over 171 kommuner → 91.5% suppression,
  only Oslo classes survive — pipeline-correct but a weak demo. Fix: `top_n_kommuner` param on
  `write_brfss_shaped_fixture` (default e.g. 12 largest) so k=10 classes survive across several
  kommuner. (omsorgsradar side unchanged.)
- **N13:** `load_icd10_codes` bad display_file → raw JSONDecodeError without the path; wrap.
- **N14:** `fetch_ssb_marginals.py` partial-fetch guard — assert fetched kommune set ⊇ KLASS set,
  else abort (silent truncated snapshot risk on regen).

## P2 — minors / polish

- FHIR `address.city` holds the kommune CODE (two agents) — resolve poststed name from snapshot or
  move code to district. UCUM: `INR`, `mL/min/1.73m2` not strictly valid codes (unused defaults).
- CI badge in README; CLI `fixtures --n 600` floods 600 FHIR bundles (cap or `--n-fhir`); PII
  receipt lacks per-type counts (omsorgsradar-side enhancement); README dtype hint
  `dtype={'state': str}` for direct CSV readers; «Thylip» varenavn — owner to verify against FEST
  (flagged low-confidence); CPT gross-error renormalization is silent (lenient-by-design? document);
  weak tests list (marginals tolerance band ±0.20, snapshot population band 3–6M) — tighten
  opportunistically.

## What passed (for the record)
fnr math vs first-principles derivation (blind), non-collision claim «convincing, verifiable in
<5 min» (blind DX), all README commands run as written, wheel works in isolation, gold labels
linguistically CORRECT on the hard cases (pseudo-negation, «ikke X, men Y») per the blind domain
reviewer, licensing/attribution coherent, no secrets, statistical sampling genuinely
snapshot-conditional.

## Recommended fix order
1. N1+N2+N3 (realism blocks — ~4 small edits + template data pass)
2. N4, N5, N7, N13, N14 (loud-failure guards)
3. N6 (century correctness + tests), N8 (test tautologies), N9 (Faker pin)
4. N10, N11, N12 (public-surface polish + demo viability)
5. P2 opportunistically. Then regenerate outputs, re-run domain spot-check, THEN PyPI.
