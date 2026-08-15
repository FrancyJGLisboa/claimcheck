"""The fact veto — prose may assert no number, quote, or date the data lacks.

Three universal, deterministic checks (no model, no network):

  - ``unsupported-figure`` (warn) — a % or magnitude in the prose that traces to
    NO number anywhere in the source data (±15%). The crown jewel: feed it any
    {data, prose} pair and it flags invented statistics.
  - ``fabricated-quote`` (error) — a long quoted span when the data carries no
    quote evidence. Any such quote is invented by construction.
  - ``date-out-of-window`` (error) — an explicit PAST date older than a stated
    window. Future dates are never flagged (they are forward-looking).

Bias is to false-NEGATIVES: an error must never kill a legitimate summary, so the
number pool is generous and the date check only fires on a clearly-parsed,
clearly-stale date.

What is NOT here, by design: contradiction checks ("prose says up, data says
down"). Those need a domain to know what "up" means. This module is only the
domain-free veto. Extracted from commodity-pulse's grounding gate.
"""

from __future__ import annotations

import re
from datetime import date
from typing import Any

# A quoted span of real length is fabricated speech when no quote evidence exists.
_QUOTE_RE = re.compile(r'["“”]([^"“”]{20,})["“”]')

_PCT_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:%|percent)")
# ≥2 digits, or any separated number. The second branch must span MULTIPLE
# separator groups: `\d[.,]\d+` stopped at the first one, so a single leading
# digit truncated `1,684,065` to `1,684` and the veto then reported a correct,
# correctly cited figure as unsupported. Broken range was 1,000,000-9,999,999
# (two leading digits took the greedy first branch, so 10,000,000 was fine) plus
# any single-leading-digit decimal — `1,234.5` and, in decimal_comma mode,
# `1.234,56`. Found 2026-08-15 against a live CFTC open-interest figure.
_MAG_RE = re.compile(r"(?<![\w./,])(\d{2}[\d.,]*|\d[.,][\d.,]*\d)(?![\w%])")
_UNIT_SUFFIX_RE = re.compile(
    r"\s?(?:kg|km|ha|mm|cm|ml|bbl|bpd|days?|weeks?|months?|years?|hours?)\b", re.IGNORECASE
)
# A real date span — mask it out before mining figures so "June 23" is not read
# as the magnitude 23.
_DATE_MASK_RE = re.compile(
    r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2}\b"
    r"|\b\d{4}-\d{2}-\d{2}\b",
    re.IGNORECASE,
)
# Keys whose numeric values are percentages/ratios — universal, not domain terms.
_PCT_KEY_TOKENS = ("pct", "percent", "yoy", "share", "ratio", "rate", "to_use")

_ISO_RE = re.compile(r"\b(\d{4}-\d{2}-\d{2})\b")
_MONTH_RE = re.compile(r"\b([A-Za-z]{3,9})\.?\s+(\d{1,2})\b")
_MONTHS = {
    "jan": 1, "january": 1, "feb": 2, "february": 2, "mar": 3, "march": 3,
    "apr": 4, "april": 4, "may": 5, "jun": 6, "june": 6, "jul": 7, "july": 7,
    "aug": 8, "august": 8, "sep": 9, "sept": 9, "september": 9, "oct": 10,
    "october": 10, "nov": 11, "november": 11, "dec": 12, "december": 12,
}


def _num(s: str, decimal_comma: bool = False) -> float | None:
    """Parse a number. EN (default): ',' = thousands, '.' = decimal.
    PT/EU (``decimal_comma``): '.' = thousands, ',' = decimal — so '63,27' is 63.27
    and '1.700' is 1700, the opposite of the EN convention."""
    try:
        s = s.rstrip(".,")
        if decimal_comma:
            return float(s.replace(".", "").replace(",", "."))
        return float(s.replace(",", ""))
    except ValueError:
        return None


def _data_numbers(data: Any) -> set[float]:
    """Every numeric value in the data, plus abs + ×1000/÷1000 twins (so prose
    '8.3 million' matches an 8263-thousand value). Generous by design."""
    nums: set[float] = set()

    def walk(o: object) -> None:
        if isinstance(o, bool):  # bool is an int subclass — never a figure
            return
        if isinstance(o, (int, float)):
            nums.add(float(o))
        elif isinstance(o, dict):
            for v in o.values():
                walk(v)
        elif isinstance(o, (list, tuple)):
            for v in o:
                walk(v)

    walk(data)
    nums |= {abs(n) for n in nums}
    big = {n for n in nums if abs(n) >= 10}
    huge = {n for n in nums if abs(n) >= 1e4}  # tonnes-scale data vs "N million" prose
    return nums | {n / 1000.0 for n in big} | {n * 1000.0 for n in big} | {n / 1e6 for n in huge}


def _data_pcts(data: Any) -> set[float]:
    """Numeric values under percent-ish keys only (narrow — no ×1000 twins). A
    fraction under such a key (0.1523) also contributes its ×100 twin so prose
    '15.2%' resolves."""
    out: set[float] = set()

    def walk(o: object) -> None:
        if isinstance(o, dict):
            for k, v in o.items():
                if (isinstance(v, (int, float)) and not isinstance(v, bool)
                        and any(t in str(k).lower() for t in _PCT_KEY_TOKENS)):
                    out.add(float(v))
                    if abs(v) <= 1:
                        out.add(float(v) * 100)
                walk(v)
        elif isinstance(o, (list, tuple)):
            for v in o:
                walk(v)

    walk(data)
    return out | {abs(n) for n in out}


def _stated_figures(text: str, decimal_comma: bool = False) -> tuple[list[float], list[float]]:
    """Prose figures split into (percentages, magnitudes). Dates are masked out
    first; unit-suffixed counts, '#'-prefixed designations and years are skipped.
    ``decimal_comma`` selects PT/EU number parsing (see ``_num``)."""
    masked = _DATE_MASK_RE.sub(" ", text)
    pcts: list[float] = []
    pct_spans: list[tuple[int, int]] = []
    for m in _PCT_RE.finditer(masked):
        v = _num(m.group(1), decimal_comma)
        if v is None:
            continue
        pcts.append(v)
        pct_spans.append((m.start(1), m.end(1)))
    mags: list[float] = []
    for m in _MAG_RE.finditer(masked):
        s = m.start(1)
        if any(a <= s < b for a, b in pct_spans):
            continue  # already counted as the numeric part of a percentage
        if s > 0 and masked[s - 1] == "#":
            continue  # a designation ('#11'), not a figure
        if _UNIT_SUFFIX_RE.match(masked, m.end(1)):
            continue  # a unit qualifier ('30 days'), not a data claim
        val = _num(m.group(1), decimal_comma)
        if val is None or (abs(val) < 10 and val == int(val)):
            continue  # small INTEGERS are counts ('3 sources'); a decimal
            # point is a data claim at any size ('$4.85/bu', ONI '-1.3')
        if val == int(val) and 1900 <= val <= 2100:
            continue  # a year, never a magnitude claim
        mags.append(val)
    return pcts, mags


def check(prose: str, data: dict[str, Any], window: tuple[str, str] | None = None,
          has_quotes: bool = False, decimal_comma: bool = False,
          tolerance: float = 0.15) -> list[dict[str, str]]:
    """Veto ``prose`` against ``data``; return findings (may be empty).

    ``window`` is an optional (from_iso, to_iso) pair enabling the stale-date
    check. ``has_quotes`` — set True when the data legitimately carries quote
    evidence, which disables the fabricated-quote check. ``decimal_comma`` — set
    True for PT/EU-formatted prose (',' = decimal, '.' = thousands), so '63,27' is
    read as 63.27 instead of 6327. Locale, not domain: it makes the veto work on
    non-US number formats without adding any domain knowledge. ``tolerance`` is the
    relative figure-match tolerance: 0.15 is the generous CI-gate default (never
    kill a legitimate summary); an *audit* — whose loss function is the opposite,
    a misstatement must be caught — wants ~0.02. The 1.0 absolute rounding floor
    scales with it, so tightening the knob tightens both.
    """
    text = prose or ""
    findings: list[dict[str, str]] = []

    def add(level: str, rule: str, term: str) -> None:
        findings.append({"level": level, "rule": rule, "term": term})

    # 1. Unsupported figure — every % / magnitude should trace to a data number.
    mag_pool = _data_numbers(data)
    pct_pool = _data_pcts(data)
    if mag_pool or pct_pool:
        floor = tolerance / 0.15  # 1.0 at the CI default; audit mode tightens it in step
        pcts, mags = _stated_figures(text, decimal_comma)
        for fig in pcts:
            tol = max(floor, tolerance * abs(fig))
            grounded = any(abs(g - fig) <= tol for g in pct_pool)
            if not grounded and abs(fig) < 10:  # small % may match a raw number
                grounded = any(abs(g - fig) <= tol for g in mag_pool)
            if not grounded:
                add("warn", "unsupported-figure", f"{fig:g}%")
        for fig in mags:
            if not any(abs(g - fig) <= max(floor, tolerance * abs(fig)) for g in mag_pool):
                add("warn", "unsupported-figure", f"{fig:g}")

    # 2. Fabricated quote — a long quoted span with no quote evidence.
    if not has_quotes:
        for q in _QUOTE_RE.findall(text):
            if len(q.split()) >= 4:
                add("error", "fabricated-quote", q[:32])
                break

    # 3. Date out of window — an explicit PAST date older than the window.
    if window:
        try:
            from_d = date.fromisoformat(window[0])
            to_d = date.fromisoformat(window[1])
        except (ValueError, TypeError):
            return findings
        for iso in _ISO_RE.findall(text):
            try:
                d = date.fromisoformat(iso)
            except ValueError:
                continue
            if d < from_d:
                add("error", "date-out-of-window", iso)
        for mo, day in _MONTH_RE.findall(text):
            num = _MONTHS.get(mo.lower())
            if not num:
                continue
            try:
                d = date(to_d.year, num, int(day))
            except ValueError:
                continue
            if d > to_d:
                continue  # future — not a stale citation
            if d < from_d:
                add("error", "date-out-of-window", f"{mo} {day}")

    return findings


def has_errors(findings: list[dict[str, str]]) -> bool:
    return any(f["level"] == "error" for f in findings)
