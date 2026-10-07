"""
Italian formatting for the text drawn in figures and written to captions
(they go into an Italian thesis): decimal comma, thousands point, euro sign
after the amount, dd/mm/yyyy dates.

Console output and the CSV/JSON tables keep the plain formats - only figure
text goes through here.
"""

import math

_SWAP = str.maketrans(",.", ".,")


def number(value: float, spec: str = "") -> str:
    """`format(value, spec)` with the separators swapped: 1,234.5 -> 1.234,5."""
    return format(value, spec).translate(_SWAP)


def pct(rate: float) -> str:
    """Whole percent, except that a rate that isn't exactly 0 or 1 never
    rounds to 0% or 100% (199/200 is not 100%): 92%, 99,5%."""
    text = f"{rate:.0%}"
    if (text == "100%" and rate < 1) or (text == "0%" and rate > 0):
        text = f"{rate:.1%}"
    return text.translate(_SWAP)


def eur(value: float) -> str:
    """Two significant figures below 1 €, cents above, whole euros from 10 €:
    5,83 €, 0,56 €, 0,0021 €, 123 €."""
    if value is None or math.isnan(value):
        return "n.d."
    if value == 0:
        return "0 €"
    if value >= 10:
        return f"{number(value, ',.0f')} €"
    digits = max(2, 1 - math.floor(math.log10(abs(value))))
    return f"{number(value, f'.{digits}f')} €"


def date(iso: str) -> str:
    """2026-09-28 -> 28/09/2026; anything else is returned unchanged."""
    parts = iso.split("-")
    if len(parts) == 3 and all(p.isdigit() for p in parts):
        return f"{parts[2]}/{parts[1]}/{parts[0]}"
    return iso
