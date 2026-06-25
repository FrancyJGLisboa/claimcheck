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

_PCT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:%|percent)")
_MAG_RE = re.compile(r"(?<![\w./,])(\d{2}[\d.,]*)(?![\w%])")  # bare numbers ≥ 2 digits
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


def _num(s: str) -> float | None:
    """Parse an EN-formatted number (',' = thousands, '.' = decimal)."""
    try:
        return float(s.rstrip(".,").replace(",", ""))
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
    return nums | {n / 1000.0 for n in big} | {n * 1000.0 for n in big}


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


def _stated_figures(text: str) -> tuple[list[float], list[float]]:
    """Prose figures split into (percentages, magnitudes). Dates are masked out
    first; unit-suffixed counts, '#'-prefixed designations and years are skipped."""
    masked = _DATE_MASK_RE.sub(" ", text)
    pcts: list[float] = []
    pct_spans: list[tuple[int, int]] = []
    for m in _PCT_RE.finditer(masked):
        try:
            pcts.append(float(m.group(1)))
        except ValueError:
            continue
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
        val = _num(m.group(1))
        if val is None or abs(val) < 10:
            continue
        if val == int(val) and 1900 <= val <= 2100:
            continue  # a year, never a magnitude claim
        mags.append(val)
    return pcts, mags


def check(prose: str, data: dict[str, Any], window: tuple[str, str] | None = None,
          has_quotes: bool = False) -> list[dict[str, str]]:
    """Veto ``prose`` against ``data``; return findings (may be empty).

    ``window`` is an optional (from_iso, to_iso) pair enabling the stale-date
    check. ``has_quotes`` — set True when the data legitimately carries quote
    evidence, which disables the fabricated-quote check.
    """
    text = prose or ""
    findings: list[dict[str, str]] = []

    def add(level: str, rule: str, term: str) -> None:
        findings.append({"level": level, "rule": rule, "term": term})

    # 1. Unsupported figure — every % / magnitude should trace to a data number.
    mag_pool = _data_numbers(data)
    pct_pool = _data_pcts(data)
    if mag_pool or pct_pool:
        pcts, mags = _stated_figures(text)
        for fig in pcts:
            tol = max(1.0, 0.15 * abs(fig))
            grounded = any(abs(g - fig) <= tol for g in pct_pool)
            if not grounded and abs(fig) < 10:  # small % may match a raw number
                grounded = any(abs(g - fig) <= tol for g in mag_pool)
            if not grounded:
                add("warn", "unsupported-figure", f"{fig:g}%")
        for fig in mags:
            if not any(abs(g - fig) <= max(1.0, 0.15 * abs(fig)) for g in mag_pool):
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
