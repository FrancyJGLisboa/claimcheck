# claimcheck

**A deterministic, no-LLM claim-vs-evidence veto.** Given some prose and the
structured data it was supposed to be written from, `claimcheck` blocks the prose
if it asserts a **number, quote, or date the data doesn't contain.**

No model. No network. No API key. ~200 lines of stdlib Python. You can read
exactly *why* it vetoed.

> **Necessary, not sufficient.** claimcheck checks *figures, not reasoning* — it
> proves no number, quote, or date was invented, **not** that the argument is sound.
> Pair it with a judgment reviewer (a human, or an adversarial LLM critic) for that.

```python
from claimcheck import check

data = {"files_changed": 3, "insertions": 88, "deletions": 12}
check("This PR adds 88 lines across 3 files.", data)   # []  → grounded
check("This PR adds 500 lines across 3 files.", data)   # [{'level':'warn','rule':'unsupported-figure','term':'500'}]
```

## Why it exists

Most LLM-output guardrails use a second model to judge the first — slow, costs
tokens, non-auditable, and itself hallucination-prone (a model checking a model).
`claimcheck` is the opposite: a **deterministic** check for the one failure mode
that matters most and is cheapest to catch — *invented figures*. Every number in
the prose must trace to a number in the source data, or it's flagged.

It does **one** thing and refuses to guess at the rest. It does *not* do semantic
contradiction ("prose says up, data says down") — that needs domain knowledge.
This is only the domain-free veto.

## The three checks

| Rule | Level | Fires when |
|---|---|---|
| `unsupported-figure` | warn | a % or magnitude in the prose traces to no number in the data (±15%) |
| `fabricated-quote` | error | a long quoted span exists but the data carries no quote evidence |
| `date-out-of-window` | error | an explicit *past* date is older than a stated window (future dates are never flagged) |

Bias is to false-negatives by design: a blocking error must never kill a
legitimate summary.

## Install

```bash
pip install claimcheck      # once published; for now: pip install git+https://github.com/FrancyJGLisboa/claimcheck
```

## CLI / CI gate

```bash
claimcheck --prose summary.md --data evidence.json          # exit 1 on errors
claimcheck --prose summary.md --data evidence.json --strict # exit 1 on warnings too
claimcheck --prose summary.md --data evidence.json --window 2026-06-01,2026-06-25
```

## GitHub Action

Block a PR when an AI-written summary invents a number:

```yaml
- uses: FrancyJGLisboa/claimcheck@v0
  with:
    prose: report.md
    data: report-data.json
    strict: "true"
```

## The receipt (opt-in second gate)

`claimcheck.receipt` is a **tamper-evident validation receipt**: proof that a
critic ran against these exact bytes and came back clean. It hashes the evidence
and the prose; edit either afterward and the receipt goes stale. `passed` is
*derived* from the findings (no high-severity finding), never asserted by the
critic — and a vacuous empty review can't rubber-stamp it. The rubric targets and
version are parameters, so it fits any domain's review checklist.

```python
from claimcheck import receipt
reasons = receipt.validate_submission(submission, required_targets=("accuracy", "completeness"),
                                      rubric_version="2026-06")
```

## Verify (the credential — no server, no trust in the issuer)

A receipt is only a credential if a stranger can confirm it **themselves**.
`reverify` re-derives one from the inputs alone: it re-hashes both files (tamper-
evidence) *and re-runs the veto* on those exact bytes. A forged `passed` receipt
over prose that asserts a quote or date the data lacks is rejected here — a clean
*judgment* can never launder prose that fails the *deterministic* floor.

```bash
# anyone holding the prose + data reproduces the verdict; exit 1 if they can't
claimcheck --verify-receipt receipt.json --prose report.md --data evidence.json
```

```python
from claimcheck import receipt
reasons = receipt.reverify(receipt.load_receipt("receipt.json"), "evidence.json", "report.md")
# []  → independently re-derived. non-empty → forged, stale, or tampered.
```

The deterministic verdict is **trustless** (anyone recomputes it). The judgment half
(an LLM critic) can't be reproduced by definition, so it's *consistency-checked*, not
re-derived — tamper-evident, not trustless. No signature needed: re-derivation is the
proof. (A signature would only add provenance for a verifier who lacks the source data.)

## Provenance

Extracted from the grounding + judgment gates of
[commodity-pulse](https://github.com/FrancyJGLisboa/commodity-pulse), where it
keeps an LLM-written market note from asserting anything the computed data
doesn't support. The architecture is the asset; this is that architecture, with
the commodities removed.

## License

MIT — see [LICENSE](LICENSE).
