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
