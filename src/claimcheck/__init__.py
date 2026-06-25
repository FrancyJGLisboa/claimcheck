"""claimcheck — a deterministic, no-LLM claim-vs-evidence veto.

Two stages, neither carrying any domain:

  check(prose, data)            — the fact veto: prose may assert no number,
                                  quote, or date the data does not contain.
  receipt.build_receipt / …     — the tamper-evident judgment receipt: proof a
                                  critic ran against these exact bytes, clean.

Extracted from commodity-pulse's grounding + judgment gates.
"""

from . import receipt
from .grounding import check, has_errors

__all__ = ["check", "has_errors", "receipt"]
__version__ = "0.1.0"
