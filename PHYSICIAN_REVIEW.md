# Physician Realism Sign-off Checklist

**Status: UNCHECKED — no realism claim is made until the owner has reviewed and checked all items.**

This document is a gate for any claim that synthdata-no generates "realistic" Norwegian health data.
Until all items below are checked by the owning physician, README and documentation must state only
that data is *structurally plausible* and *template-based* — not that it represents realistic Norwegian EPJ/journal text or realistic patient populations.

Reviewed by: ___________________________ (utdannet lege, master i medisin)
Date: ___________________________

---

## Family 1: Persons

- [ ] Norwegian name distribution: do generated names look plausible for the Norwegian population (not dominated by very rare or foreign names)?
- [ ] Address and postal code formats: do addresses follow Norwegian street/postal conventions?
- [ ] Birth date and age distribution: are generated ages plausible for the configured birth-year range (1930–2005)?
- [ ] Kommune assignment: do the kommune codes correspond to real Norwegian municipalities?
- [ ] Fnr structure: verify with a Tenor-range example that month ∈ 81–92 and checksum is valid (use `ids.valid_fnr_checksum()`).

---

## Family 2: Tabular

- [ ] Diabetes prevalence: do default CPT values (≈10% age 18–44, ≈30% age 45–64, ≈45% age 65–95) fall within a plausible range compared to known Norwegian KOSTRA/HUNT aggregates?
- [ ] `tjeneste_bruk` distribution: does the approximate prevalence match general knowledge of Norwegian elder-care uptake?
- [ ] `diagnosekategori` (1–4) distribution: are the relative proportions broadly defensible as a proxy for diagnostic complexity strata?
- [ ] Notes column: are planted Tenor-range fnr detectable by omsorgsradar's anonymize pipeline? (Cross-check: run the brfss-demo pipeline against the generated fixture.)
- [ ] Age marginals: do generated age/sex distributions per kommune follow SSB 07459 shapes (younger cities, older rural municipalities)?

---

## Family 3: Clinical text (bokmål)

- [ ] Negation templates: are the bokmål negation cues (`ikke`, `ingen tegn til`, `uten`, `fri for`, `mangler`, `benektes`, `u.a.`, `i.a.b.`) grammatically correct and clinically natural?
- [ ] Pseudo-negation traps: do `kan ikke utelukkes` and `ikke utelukket` correctly map to POSSIBLE_EXISTENCE (not NEGATED_EXISTENCE)?
- [ ] Uncertainty cues: are `mistanke om`, `mulig`, `suspekt`, `sannsynlig`, `obs mulig` used in clinical Norwegian the way a practitioner would write them?
- [ ] Historical context: do `tidligere`, `gjennomgikk`, `anamnestisk` frames look like EPJ-style historical references?
- [ ] Family history: do `mor/far/søsken har` and `hereditet for` frames match standard Norwegian family history notation?
- [ ] Abbreviations: are `ca.`, `pas.`, `bt.`, `temp.`, `evt.`, `pga.`, `tbl.`, `i.v.` used in contexts where a Norwegian clinician would naturally use them?
- [ ] Section headers: do the 15 section-header families (ANAMNESE, VURDERING, DIAGNOSE, PLAN, etc.) match headers seen in Norwegian EPJ systems (Helseplattformen, DIPS, Doctorway)?
- [ ] Entity slot fillers: are the condition/symptom names used in templates neutral, common Norwegian words with no licensing concerns?
- [ ] Overall register: does the text read like terse Norwegian clinical documentation (not like consumer health text or English-translated text)?

---

## Family 4: FHIR

- [ ] Patient.identifier: verify that the identifier system OID (`urn:oid:2.16.578.1.12.4.1.4.1` for fnr, `…4.2` for D-nr) matches the no-basis-Patient profile requirement.
- [ ] Medication coding: does each Medication resource carry both a FEST coding (`http://ehelse.no/fhir/CodeSystem/FEST`) and an ATC coding (`http://www.whocc.no/atc`)? Does the ATC code look plausible (e.g., `N02BE01` for paracetamol)?
- [ ] Condition coding: is the ICD-10-NO OID correct (`urn:oid:2.16.578.1.12.4.1.1.7110`)? Are the generated codes valid ICD-10 codes (no display names — codes only)?
- [ ] Observation values: are the default creatinine values (85.0 µmol/L) and units (`umol/L`) in a plausible clinical range?
- [ ] Bundle structure: does the transaction bundle's `entry[].request.method = PUT` and `fullUrl = urn:uuid:…` pattern match what HAPI R4 expects?
- [ ] No real-person data: confirm no template, snapshot, or generated value was derived from or matches a real patient record.

---

## Sign-off statement

By checking all items above, I confirm that:
1. The generated data is *structurally plausible* as synthetic Norwegian health data.
2. No item above revealed a structural error that would make the data unsuitable for NLP evaluation or system-testing purposes.
3. I have NOT verified that the default CPT values or marginals are epidemiologically accurate — they are documented as approximate.
4. No real patient data was used in the generation of any template, snapshot, or code list.

Signature: ___________________________ Date: ___________________________
