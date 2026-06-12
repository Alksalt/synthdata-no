# Third-party sources

## FEST data (ATC codes + varenavn)

- **Source:** FEST (Forskrivnings- og ekspedisjonsstøtte), published by Direktoratet for
  medisinske produkter (DMP), https://www.dmp.no — distributed via
  `https://fest.legemiddelverket.no/Fest/FestService250.svc` (SOAP, GetM30).
- **License:** Norwegian Licence for Open Government Data (NLOD) 2.0 —
  https://data.norge.no/nlod/en/2.0. Free copy/modify/redistribute with attribution.
- **Attribution (use verbatim on every artifact):** "Contains data from FEST
  (Forskrivnings- og ekspedisjonsstøtte), published by Direktoratet for medisinske produkter
  (DMP), made available under NLOD 2.0. DMP is the source; DMP does not endorse synthdata-no
  or this derived dataset."
- **Norwegian variant:** "Inneholder data fra FEST, utgitt av Direktoratet for medisinske
  produkter (DMP), tilgjengeliggjort under Norsk lisens for offentlige data (NLOD) 2.0. DMP
  er kilden og har ikke godkjent synthdata-no eller dette avledede datasettet."
- File: `src/synthdata_no/data/atc_fest.json`
- Regenerate: `uv run python scripts/extract_fest_codes.py /path/to/full_fest.xml`

## LOINC codes

- **Source:** LOINC® — Regenstrief Institute, Inc., https://loinc.org
- **License:** Regenstrief LOINC License — free distribution with verbatim attribution notice.
  Full license: https://loinc.org/license/
- **Attribution (verbatim, required):** "This content includes LOINC codes from the LOINC
  table, the LOINC panels and forms file, LOINC answer file, and/or the LOINC Part file, as
  applicable. This content is copyright © 1995 Regenstrief Institute, Inc. and the LOINC
  Committee, and available at no cost under the license at https://loinc.org/license/.
  LOINC® is a registered United States trademark of Regenstrief Institute, Inc."
- File: `src/synthdata_no/data/loinc_min.json`

## ICD-10 codes

- **Source:** WHO International Classification of Diseases, 10th Revision (ICD-10),
  Version 2019. World Health Organization (WHO), https://icd.who.int/browse10/
- **License:** WHO CC BY-ND 3.0 IGO — verbatim redistribution of alphanumeric codes is
  permitted; adaptation (e.g. translation into Norwegian) is not. This package redistributes
  codes only — NO Norwegian or English display names are embedded.
- **Rationale for code-only approach:** Norwegian display names are a national-level
  translation that would constitute an "adaptation" under CC BY-ND 3.0 IGO without explicit
  WHO permission. We redistribute codes only and support user-supplied display files.
- File: `src/synthdata_no/data/icd10_codes.json`

## SSB KLASS (kommuner)

- **Source:** Statistics Norway (SSB), KLASS classification 131 (Kommuner i Norge),
  https://data.ssb.no/api/klass/v1/classifications/131
- **License:** Norwegian Licence for Open Government Data (NLOD) 2.0 / CC BY 4.0 (SSB)
- **Attribution:** Statistics Norway (SSB), data.ssb.no/api/klass, classification 131.
- File: `src/synthdata_no/data/klass_131_snapshot.json`
- Regenerate: `uv run python scripts/fetch_klass_snapshot.py`

## Checksum logic (vendored from omsorgsradar)

- **Source:** `omsorgsradar/src/omsorgsradar/core/anonymize/pii.py` by Oleksandr Altukhov
  (project: omsorgsradar, https://github.com/Alksalt/omsorgsradar)
- **License:** MIT-compatible (same author)
- Vendored functions: `append_fnr_control_digits`, `valid_fnr_checksum`, `_FNR_K1_W`, `_FNR_K2_W`
- Attribution comment in: `src/synthdata_no/ids.py`
