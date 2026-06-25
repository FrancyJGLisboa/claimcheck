# claimcheck

**A deterministic, no-LLM claim-vs-evidence veto.** Given some prose and the
structured data it was supposed to be written from, `claimcheck` blocks the prose
if it asserts a **number, quote, or date the data doesn't contain.**

No model. No network. No API key. ~200 lines of stdlib Python. You can read
exactly *why* it vetoed.

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

## Provenance

Extracted from the grounding + judgment gates of
[commodity-pulse](https://github.com/FrancyJGLisboa/commodity-pulse), where it
keeps an LLM-written market note from asserting anything the computed data
doesn't support. The architecture is the asset; this is that architecture, with
the commodities removed.

## License

MIT — see [LICENSE](LICENSE).
