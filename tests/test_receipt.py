from claimcheck import receipt

# Any domain's rubric — proving the module carries no domain itself.
TARGETS = ("accuracy", "completeness")
VERSION = "2026-06"


def _files(tmp_path):
    ev = tmp_path / "evidence.json"
    ev.write_text('{"x": 1}')
    pr = tmp_path / "prose.md"
    pr.write_text("the prose")
    return str(ev), str(pr)


def _clean_submission():
    return {
        "rubric_version": VERSION,
        "review": [{"target": t, "verdict": "ok"} for t in TARGETS],
        "findings": [],
    }


def test_clean_review_mints_passing_receipt(tmp_path):
    ev, pr = _files(tmp_path)
    sub = _clean_submission()
    assert receipt.validate_submission(sub, TARGETS, VERSION) == []
    r = receipt.build_receipt(ev, pr, sub)
    assert r["passed"] is True
    assert receipt.verify_receipt(r, ev, pr, VERSION) == []


def test_tampering_with_prose_is_detected(tmp_path):
    ev, pr = _files(tmp_path)
    r = receipt.build_receipt(ev, pr, _clean_submission())
    (tmp_path / "prose.md").write_text("edited after the critic ran")
    assert any("prose hash mismatch" in x for x in receipt.verify_receipt(r, ev, pr, VERSION))


def test_bare_array_fails_anti_vacuous():
    assert receipt.validate_submission([], TARGETS, VERSION)


def test_missing_required_target_fails():
    sub = {"rubric_version": VERSION,
           "review": [{"target": "accuracy", "verdict": "ok"}], "findings": []}
    assert any("required targets" in x for x in receipt.validate_submission(sub, TARGETS, VERSION))


def test_stale_rubric_fails():
    sub = {**_clean_submission(), "rubric_version": "2020-01"}
    assert any("rubric_version" in x for x in receipt.validate_submission(sub, TARGETS, VERSION))


def test_high_finding_derives_failed_verdict(tmp_path):
    ev, pr = _files(tmp_path)
    # passed is DERIVED — the critic cannot assert passed:true over a real high.
    r = receipt.build_receipt(ev, pr, {"findings": [{"severity": "high"}]})
    assert r["passed"] is False


# --- reverify: the credential — independently re-derivable, no trust in the issuer ----

def test_reverify_passes_on_untampered_receipt(tmp_path):
    ev, pr = _files(tmp_path)                       # prose "the prose" — no figures/quotes/dates
    r = receipt.build_receipt(ev, pr, _clean_submission())
    assert receipt.reverify(r, ev, pr) == []


def test_reverify_detects_edited_prose(tmp_path):
    ev, pr = _files(tmp_path)
    r = receipt.build_receipt(ev, pr, _clean_submission())
    (tmp_path / "prose.md").write_text("edited after the receipt was minted")
    assert any("prose hash mismatch" in x for x in receipt.reverify(r, ev, pr))


def test_reverify_rejects_forged_receipt_over_lying_prose(tmp_path):
    # THE credential property: a clean *judgment* receipt cannot launder prose that
    # fails the *deterministic* veto. Prose asserts a quote the data has no evidence
    # for → re-running check() recomputes the block, so the forged 'passed' is rejected.
    ev = tmp_path / "e.json"; ev.write_text('{"x": 1}')
    pr = tmp_path / "p.md"
    pr.write_text('The CEO said "we will double revenue next year, guaranteed".')
    forged = receipt.build_receipt(str(ev), str(pr), _clean_submission())
    assert forged["passed"] is True                # the judgment half looks clean...
    reasons = receipt.reverify(forged, str(ev), str(pr))
    assert any("re-derivation FAILED" in x for x in reasons)   # ...but the floor re-derives the lie


def test_reverify_catches_passed_contradicting_recorded_findings(tmp_path):
    ev, pr = _files(tmp_path)
    r = receipt.build_receipt(ev, pr, {"findings": [{"severity": "high", "detail": "real high"}]})
    r["passed"] = True                             # hand-forge the verdict
    assert any("contradicts" in x for x in receipt.reverify(r, ev, pr))
