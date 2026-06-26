from claimcheck import check, has_errors


def test_unsupported_figure_flags_invented_number():
    data = {"price": {"pct_change": -10.4}}
    out = check("It fell 47%.", data)
    assert any(f["rule"] == "unsupported-figure" and f["term"] == "47%" for f in out), out


def test_grounded_figure_passes():
    data = {"price": {"pct_change": -10.4}}
    assert check("It fell 10.4%.", data) == []


def test_works_on_non_commodity_domain():
    # Same code, different data shape: a PR description vs diff stats.
    data = {"files_changed": 3, "insertions": 88, "deletions": 12}
    assert any(f["term"] == "500" for f in check("Adds 500 lines.", data))
    assert check("Adds 88 lines, removes 12.", data) == []


def test_fabricated_quote_is_error():
    out = check('She said "this is the worst harvest in living memory".', {})
    assert has_errors(out), out


def test_has_quotes_disables_quote_check():
    assert check('She said "this is the worst harvest in living memory".', {}, has_quotes=True) == []


def test_stale_date_in_window_blocks():
    win = ("2026-06-01", "2026-06-25")
    out = check("As reported on 2026-01-10.", {}, window=win)
    assert any(f["rule"] == "date-out-of-window" for f in out), out


def test_in_window_date_ok():
    win = ("2026-06-01", "2026-06-25")
    assert check("As reported on 2026-06-10.", {}, window=win) == []


def test_future_date_not_flagged():
    win = ("2026-06-01", "2026-06-25")
    assert check("A catalyst lands July 4.", {}, window=win) == []


# --- locale: PT/EU number format (',' = decimal, '.' = thousands) ---------------

def test_pt_decimal_comma_reads_figures_correctly():
    from claimcheck import check
    data = {"price": 63.27, "move_pct": 6.8, "freight": 29.4}
    prose = "O preço foi R$63,27, com alta de 6,8% e frete de R$29,40."
    # WRONG locale (default EN) misreads 63,27 as 6327 → spurious unsupported-figure
    assert any(f["rule"] == "unsupported-figure" for f in check(prose, data))
    # CORRECT locale reads them as 63.27 / 6.8 / 29.4 → clean
    assert check(prose, data, decimal_comma=True) == []


def test_pt_thousands_dot_is_not_a_decimal():
    from claimcheck import check
    data = {"volume": 1700}
    # PT '1.700' is 1700 (thousands dot), not 1.7
    assert check("Volume de 1.700 toneladas.", data, decimal_comma=True) == []
