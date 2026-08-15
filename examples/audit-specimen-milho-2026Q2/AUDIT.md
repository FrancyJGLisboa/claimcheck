# Factual-Fidelity Inspection Report — Specimen

**Subject:** AI-assisted market brief *"Milho recua puxado por Chicago…"* (safra-brief, corn, Brazil)
**Report date of subject:** 2026-06-25 · **Inspection date:** 2026-07-22
**Method:** claimcheck deterministic figure veto, audit mode (tolerance 2%)
**Independence:** **Second-party review.** The subject brief was produced by the reviewer's own tooling (safra-brief). This specimen demonstrates method, not independence. A client engagement is either performed on systems the reviewer did not build, or carries this same disclosure in the engagement letter.

## 1. Scope

One AI-written market brief and the structured evidence scaffold it was generated from (CEPEA/ESALQ cash, CBOT futures, CONAB balance/levantamento/cost/freight, CFTC COT, Secex/MDIC exports, Open-Meteo weather). The inspection checks **factual fidelity only**: does every number, quote, and date asserted in the prose trace to the evidence? It does not assess whether the analysis or its reasoning is sound (see Limitations).

## 2. Sampling method

Exhaustive, not sampled: every figure the prose asserts is machine-extracted and tested — 8 percentages and 15 magnitudes, **23 figures** in total — plus all quoted spans and all explicit dates. A stated figure passes if it matches an evidence value within ±2% (with unit-rescale twins ×/÷10³ and ÷10⁶, so "140,5 milhões de toneladas" tests against 140 463,1 kt).

## 3. Findings

| Check | Tested | Passed | Failed |
|---|---|---|---|
| Figure traces to evidence (±2%) | 23 | 23 | 0 |
| Quoted spans backed by quote evidence | 0 found | — | 0 |
| Dates within stated window | all explicit dates | all | 0 |

## 4. Discrepancy register

None for the subject brief. **Detection capability was demonstrated on a seeded control** (`holdout-seeded-brief.md`): the same brief with two deliberately misstated figures — production 140,5 → 133,1 Mt (−5,3%) and exports 7,47 → 7,12 Mt (−4,7%). Audit mode flagged both; a standard 15%-tolerance CI run flagged neither. The control is a holdout: it is never used to tune the tool, only to score it.

## 5. Opinion

Every figure, quote, and date asserted in the subject brief traces to its evidence scaffold within a 2% tolerance. On factual fidelity — and on factual fidelity only — the brief is faithful to its sources as of 2026-06-25.

## 6. Limitations

- **Figures, not reasoning.** A brief can be arithmetically faithful and analytically wrong; direction claims ("led by Chicago"), causal claims, and forecasts are outside this inspection. Forecast calibration is scored separately when outcomes land.
- **Detection floor.** A misstated figure lying within ~2% of *any* value in the evidence pool is undetectable by this method. The pool here contains a 9-survey CONAB history spanning 138,3–140,5 Mt, so production misstatements inside that band would not be caught. The seeded control was sized (≈5%) to sit above this floor.
- **Scaffold provenance not audited.** The inspection verifies prose against the scaffold, not the scaffold against CONAB/CFTC/Secex primary documents. That upstream extraction is a separate engagement step.

## 7. Reproduction (no trust in the issuer required)

Anyone holding the three files re-derives this verdict:

```bash
claimcheck --prose brief.md --data scaffold.json --decimal-comma --tolerance 0.02 --strict   # exit 0
claimcheck --verify-receipt audit-receipt.json --prose brief.md --data scaffold.json          # exit 0
claimcheck --prose holdout-seeded-brief.md --data scaffold.json --decimal-comma --tolerance 0.02 --strict  # exit 1, 2 findings
```

The receipt (`audit-receipt.json`) binds the exact bytes and the tolerance used; edit any input and re-verification fails.
