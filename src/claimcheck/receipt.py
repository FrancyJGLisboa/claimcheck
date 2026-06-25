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


def build_receipt(evidence_path: str, prose_path: str, submission: Any) -> dict:
    """Compute the receipt from the two files + the critic's submission.

    Accepts the full submission object (``{rubric_version, review, findings}``) or,
    for library-level callers, a bare findings list. ``passed`` is derived (no
    high-severity finding), never taken from input.
    """
    if isinstance(submission, list):  # library convenience: a bare findings list
        submission = {"findings": submission}
    findings = submission.get("findings") or []
    n_high = sum(1 for f in findings if _is_high(f))
    return {
        "evidence_sha": sha256_file(evidence_path),
        "prose_sha": sha256_file(prose_path),
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


def load_receipt(path: str) -> Any:
    """Load a receipt JSON file; raises on missing/unreadable file (caller blocks)."""
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)
