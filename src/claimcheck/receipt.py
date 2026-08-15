"""Tamper-evident validation receipt — proof a critic ran against these bytes.

The fact veto (``grounding.check``) proves prose does not contradict the data;
this is the second, opt-in gate: proof that a critique step actually ran against
THESE exact bytes and recorded no high-severity finding. It does not prove the
critique was *good* — only that it happened against the right inputs and came
back clean.

Tamper-evidence comes from hashing the two files the critic saw. Edit either
after the critic ran and its sha256 no longer matches the receipt, so the receipt
reads as stale and the caller blocks.

``passed`` is DERIVED here, never asserted by the critic. Anti-vacuous contract:
a bare ``[]`` does not pass — the critic must submit a per-dimension ``review``
covering every required target plus the ``rubric_version`` it judged against. The
ONLY domain coupling — the target list and the rubric version — are parameters
here, not hardcoded constants. Extracted from commodity-pulse's judgment gate.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

from .grounding import check, has_errors

_SEVERITIES = ("high", "med", "low")
_VERDICTS = ("ok", "finding")


def sha256_file(path: str) -> str:
    """Hex sha256 of a file's raw bytes."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def _is_high(finding: Any) -> bool:
    return isinstance(finding, dict) and str(finding.get("severity", "")).lower() == "high"


def validate_findings(findings: Any) -> list[str]:
    """Schema-check the critic's findings; return reasons (empty == valid).

    Fails CLOSED: a malformed findings file must never be silently treated as
    "zero highs → passed". An unknown severity could hide a real high under a typo.
    """
    if not isinstance(findings, list):
        return ["findings is not a JSON array"]
    reasons: list[str] = []
    for i, f in enumerate(findings):
        if not isinstance(f, dict):
            reasons.append(f"finding[{i}] is not an object")
            continue
        sev = str(f.get("severity", "")).lower()
        if sev not in _SEVERITIES:
            reasons.append(f"finding[{i}] has invalid severity {f.get('severity')!r} (want high|med|low)")
    return reasons


def validate_submission(submission: Any, required_targets: tuple[str, ...],
                        rubric_version: str) -> list[str]:
    """Schema-check the critic's full submission; return reasons (empty == valid).

    Fails CLOSED on a vacuous or incomplete review: the submission must be an
    object carrying the current ``rubric_version``, a ``review`` that addresses
    EVERY ``required_targets`` entry with an ok/finding verdict, and a well-formed
    ``findings`` list. A bare findings array does not pass — the anti-vacuous bar.
    """
    if not isinstance(submission, dict):
        return ["submission must be an object with `review` + `findings` "
                "(a bare findings array does not pass the anti-vacuous contract)"]
    reasons: list[str] = []
    rv = submission.get("rubric_version")
    if rv != rubric_version:
        reasons.append(f"rubric_version {rv!r} != current {rubric_version!r} "
                       "(absent or stale — re-review against the current rubric)")
    review = submission.get("review")
    if not isinstance(review, list):
        reasons.append("`review` is missing or not a JSON array")
    else:
        covered: set[str] = set()
        for i, r in enumerate(review):
            if not isinstance(r, dict):
                reasons.append(f"review[{i}] is not an object")
                continue
            if str(r.get("verdict", "")).lower() not in _VERDICTS:
                reasons.append(f"review[{i}] verdict {r.get('verdict')!r} not in {_VERDICTS}")
            covered.add(str(r.get("target", "")))
        missing = [t for t in required_targets if t not in covered]
        if missing:
            reasons.append(f"review does not address required targets: {missing}")
    reasons += validate_findings(submission.get("findings", []))
    return reasons


def build_receipt(evidence_path: str, prose_path: str, submission: Any,
                  window: tuple[str, str] | None = None, has_quotes: bool = False,
                  decimal_comma: bool = False, tolerance: float = 0.15) -> dict:
    """Compute the receipt from the two files + the critic's submission.

    Accepts the full submission object (``{rubric_version, review, findings}``) or,
    for library-level callers, a bare findings list. ``passed`` is derived (no
    high-severity finding), never taken from input.

    ``window``/``has_quotes`` are the deterministic-check parameters; they are recorded
    under ``config`` so a third party can RE-RUN the same veto from the receipt alone
    (see ``reverify``). The recorded ``claimcheck_version`` is provenance, not trust.
    """
    if isinstance(submission, list):  # library convenience: a bare findings list
        submission = {"findings": submission}
    findings = submission.get("findings") or []
    n_high = sum(1 for f in findings if _is_high(f))
    try:  # deferred: __version__ is set after this module imports in __init__
        from claimcheck import __version__ as _v
    except Exception:  # pragma: no cover
        _v = None
    return {
        "claimcheck_version": _v,
        "evidence_sha": sha256_file(evidence_path),
        "prose_sha": sha256_file(prose_path),
        "config": {"window": list(window) if window else None, "has_quotes": bool(has_quotes),
                   "decimal_comma": bool(decimal_comma), "tolerance": float(tolerance)},
        "passed": n_high == 0,
        "n_high": n_high,
        "rubric_version": submission.get("rubric_version"),
        "critic": submission.get("critic"),
        "review": submission.get("review"),
        "findings": findings,
    }


def verify_receipt(receipt: Any, evidence_path: str, prose_path: str,
                   rubric_version: str) -> list[str]:
    """Return failure reasons (empty == the receipt is valid).

    Fails closed: a malformed receipt, a stale hash, a failed verdict, or a stale
    rubric each yields a reason. The caller blocks on any non-empty result.
    """
    reasons: list[str] = []
    if not isinstance(receipt, dict):
        return ["receipt is not a JSON object"]
    if receipt.get("evidence_sha") != sha256_file(evidence_path):
        reasons.append("evidence hash mismatch — the evidence changed since validation (stale receipt)")
    if receipt.get("prose_sha") != sha256_file(prose_path):
        reasons.append("prose hash mismatch — the prose changed since validation (stale receipt)")
    if receipt.get("passed") is not True:
        reasons.append("receipt verdict is not passed — high-severity findings were recorded")
    if receipt.get("rubric_version") != rubric_version:
        reasons.append(f"receipt rubric_version {receipt.get('rubric_version')!r} != current "
                       f"{rubric_version!r} — the rubric changed since validation; re-review")
    return reasons


def reverify(receipt: Any, evidence_path: str, prose_path: str) -> list[str]:
    """Independently RE-DERIVE a receipt — no server, no trust in the issuer.

    This is the credential check (vs ``verify_receipt``, which asks "is this fresh
    against the current rubric"). Anyone holding the two files reproduces the verdict:

    1. **Tamper-evidence** — re-hash both files; they must be the bytes the receipt bound.
    2. **Deterministic re-derivation** — RE-RUN ``check()`` on those exact bytes using the
       recorded ``config``. A forged ``passed`` receipt over prose that asserts a quote or
       date the data lacks is rejected HERE, because the veto recomputes the same block.
       (A clean *judgment* can never launder prose that fails the *deterministic* floor.)
    3. **Judgment consistency** — the LLM critic cannot be reproduced by definition, so its
       half is only consistency-checked: ``n_high`` recomputed from the recorded findings
       must agree with the derived ``passed``. This is the honest ceiling — the deterministic
       verdict is trustless; the judgment attestation is tamper-evident, not reproducible.

    Empty == independently verified. Any reason → the caller blocks.
    """
    reasons: list[str] = []
    if not isinstance(receipt, dict):
        return ["receipt is not a JSON object"]

    if receipt.get("evidence_sha") != sha256_file(evidence_path):
        reasons.append("evidence hash mismatch — these are not the bytes the receipt bound")
    if receipt.get("prose_sha") != sha256_file(prose_path):
        reasons.append("prose hash mismatch — these are not the bytes the receipt bound")

    cfg = receipt.get("config") or {}
    win = cfg.get("window")
    window = (win[0], win[1]) if isinstance(win, (list, tuple)) and len(win) == 2 else None
    with open(prose_path, encoding="utf-8") as fh:
        prose = fh.read()
    with open(evidence_path, encoding="utf-8") as fh:
        data = json.load(fh)
    rederived = check(prose, data, window=window, has_quotes=bool(cfg.get("has_quotes")),
                      decimal_comma=bool(cfg.get("decimal_comma")),
                      tolerance=float(cfg.get("tolerance", 0.15)))
    if has_errors(rederived):
        bad = ", ".join(f"{f['rule']}:{f['term']}" for f in rederived if f["level"] == "error")
        reasons.append(f"deterministic re-derivation FAILED — the veto blocks these bytes ({bad}); "
                       "a passing receipt over them is forged or stale")

    findings = receipt.get("findings")
    if not isinstance(findings, list):
        reasons.append("receipt findings missing or not a JSON array")
    else:
        n_high = sum(1 for f in findings if _is_high(f))
        if receipt.get("passed") is not (n_high == 0):
            reasons.append(f"passed={receipt.get('passed')!r} contradicts {n_high} "
                           "high-severity finding(s) recorded in the receipt")
        if receipt.get("n_high") not in (None, n_high):
            reasons.append(f"recorded n_high={receipt.get('n_high')} != {n_high} recomputed from findings")
    return reasons


def load_receipt(path: str) -> Any:
    """Load a receipt JSON file; raises on missing/unreadable file (caller blocks)."""
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)
