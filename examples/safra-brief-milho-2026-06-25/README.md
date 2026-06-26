# A publicly verifiable brief — milho (corn), 2026-06-25

A real [safra-brief](https://github.com/FrancyJGLisboa/commodity-pulse) market note,
published with its evidence and a claimcheck receipt so **you can verify it yourself** —
no server, no account, no trust in whoever published it.

| file | what it is |
|---|---|
| `scaffold.json` | the **evidence**: every number, computed from public CEPEA/CONAB/CFTC data |
| `brief.md` | the **prose**: the analyst narrative written from that scaffold |
| `receipt.json` | the **credential**: hashes of both files + the recorded review |

## Verify it

```bash
pip install git+https://github.com/FrancyJGLisboa/claimcheck
claimcheck --verify-receipt receipt.json --prose brief.md --data scaffold.json
# claimcheck verify: OK — receipt re-derived from --prose/--data, no trust required
```

`verify` re-hashes both files (tamper-evidence) **and re-runs the figure veto** on these
exact bytes — every percentage and magnitude in the prose is re-checked against the
scaffold (PT number format, `,` = decimal). The receipt's `passed` is not taken on faith;
it is recomputed in front of you.

## Break it (so you trust the OK)

```bash
sed 's/R\$63,27/R\$70,00/' brief.md > tampered.md
claimcheck --verify-receipt receipt.json --prose tampered.md --data scaffold.json
# [verify] prose hash mismatch — these are not the bytes the receipt bound
# claimcheck verify: FAILED          (exit 1)
```

Change one figure and it fails. A forged `passed` receipt over prose that asserts a number
the scaffold doesn't contain fails too — `verify` re-derives the veto, so a clean *judgment*
can't launder a bad *number*.

## What the receipt does and doesn't prove

- **Proves (trustless):** every figure in the prose traces to a number in the evidence, and
  neither file was altered after the receipt was minted. Anyone reproduces this.
- **Does not prove:** that the evidence itself is right, or that the *reasoning* is sound.
  The recorded review (an independent critic, 2 rounds) is tamper-evident but **not
  reproducible** — an LLM judging an LLM can't be re-run to the same bytes. Figures, not
  reasoning. See claimcheck's [necessary-not-sufficient](../../README.md) note.
