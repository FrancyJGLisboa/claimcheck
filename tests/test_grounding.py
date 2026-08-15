from claimcheck import check, has_errors
from claimcheck.grounding import _stated_figures


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


# --- small decimals: a decimal point makes a figure, whatever its size ----------

def test_small_decimal_is_flagged_when_unsupported():
    # Audit replay (bellwether 2026-07-20): a fabricated "$4.85 per bushel" farm
    # price and an ONI of "-1.3" both sailed through GROUNDED because the <10
    # noise floor swallowed every decimal. A decimal is a data claim, not a count.
    finds = check("Farm price pegged at $4.85 per bushel.", {"stocks": 2756})
    assert {"level": "warn", "rule": "unsupported-figure", "term": "4.85"} in finds


def test_small_decimal_grounds_against_data():
    assert check("ONI came in at -1.3 for the season.", {"oni": -1.3}) == []


def test_small_integer_counts_stay_skipped():
    # "3 sources", "5 states" are counts — the noise floor still holds for integers
    assert check("Reviewed 3 sources across 5 states.", {"stocks": 2756}) == []


# --- audit mode: tighter tolerance for inspection work, not CI gating -----------

def test_audit_tolerance_catches_misstatement_ci_mode_forgives():
    # A 2.5% misstatement of a crop figure: fine for a CI gate, a finding for an audit.
    data = {"production_kt": 140463}
    prose = "Production came in at 137,000 kt."
    assert check(prose, data) == []
    finds = check(prose, data, tolerance=0.02)
    assert any(f["rule"] == "unsupported-figure" and f["term"] == "137000" for f in finds), finds


def test_millions_twin_grounds_tonnes_scale_data():
    # Prose says "7.47 million tonnes"; data records 7468718.5 tonnes. One ×1000
    # hop isn't enough — the ÷1e6 twin must ground it, even at audit tolerance.
    data = {"ytd_t": 7468718.5}
    assert check("Exports totaling 7.47 million tonnes.", data, tolerance=0.02) == []


def test_audit_floor_scales_with_tolerance():
    # Rounding 0.21 → "0.2%" must still pass an audit; a wrong "0.9%" must not.
    data = {"rev_pct": 0.21}
    assert check("A revision of 0.2%.", data, tolerance=0.02) == []
    assert check("A revision of 0.9%.", data) == []  # CI floor of 1.0 forgives it
    assert any(f["term"] == "0.9%" for f in check("A revision of 0.9%.", data, tolerance=0.02))


# --- thousands separators: the second group must not truncate the figure --------

def test_millions_with_separators_are_read_whole():
    """The regression: `\\d[.,]\\d+` stopped at the FIRST separator group, so a
    single leading digit truncated 1,684,065 to 1,684. Two leading digits took
    the greedy branch, so 10,000,000 always worked — which is why fixtures under
    a million never caught it. Found against a live CFTC open-interest value.

    NOTE this assertion passes even against the OLD regex, and that is exactly
    why the bug survived here: truncating at the second separator yields
    value/1000, which is precisely the x1000 twin `_data_numbers` already
    admits. claimcheck's own tolerance masks its own extractor. The bug only
    became visible in a consumer whose figure match is EXACT (bellwether's
    `_close`, rel=0), where 1684 does not equal 1684.065. The tests that can
    actually fail assert `_stated_figures` directly, below."""
    data = {"open_interest": 1684065}
    assert check("Open interest was 1,684,065 contracts.", data) == []
    assert check("Open interest was 1684065 contracts.", data) == []


def test_the_whole_broken_range_round_trips():
    for literal, value in (("999,999", 999999), ("1,000,000", 1000000),
                           ("1,684,065", 1684065), ("9,999,999", 9999999),
                           ("10,000,000", 10000000), ("12,345,678", 12345678)):
        assert _stated_figures(literal)[1] == [float(value)], literal


def test_single_leading_digit_decimal_keeps_its_fraction():
    # `1,234.5` truncated to 1,234 — the fractional part was silently dropped.
    assert _stated_figures("1,234.5")[1] == [1234.5]


def test_eu_format_millions_are_read_whole():
    # decimal_comma mode had the same truncation: 1.234,56 -> 1.234 -> 1234.
    assert _stated_figures("1.234,56", decimal_comma=True)[1] == [1234.56]


def test_a_bare_single_digit_is_still_not_a_figure():
    # The widened branch must not start treating "3 sources" as a data claim.
    assert _stated_figures("Reviewed 3 sources.")[1] == []
