"""French number formatting for the V2 interface (decimal comma, narrow no-break spaces, minus sign)."""
from __future__ import annotations

import math

import pandas as pd

NBSP = " "       # before % and €
THIN = " "       # thousands separator
MINUS = "−"
MONTHS = ("janv.", "févr.", "mars", "avr.", "mai", "juin", "juil.", "août", "sept.", "oct.", "nov.", "déc.")


def _missing(x) -> bool:
    return x is None or (isinstance(x, float) and math.isnan(x)) or (not isinstance(x, str) and pd.isna(x))


def _sign(text: str) -> str:
    return text.replace("-", MINUS)


def num(x, digits: int = 2, sign: bool = False) -> str:
    if _missing(x):
        return "—"
    if round(float(x), digits) == 0:          # no "−0" / "−0,0"
        x = 0.0
    text = f"{x:+,.{digits}f}" if sign else f"{x:,.{digits}f}"
    return _sign(text.replace(",", "_").replace(".", ",").replace("_", THIN))


def pct(x, digits: int = 1, sign: bool = False) -> str:
    return "—" if _missing(x) else f"{num(x * 100, digits, sign)}{NBSP}%"


def pts(x, digits: int = 1) -> str:
    return "—" if _missing(x) else f"{num(x * 100, digits, True)}{NBSP}pt"


def eur(x, sign: bool = False) -> str:
    return "—" if _missing(x) else f"{num(x, 0, sign)}{NBSP}€"


def keur(x) -> str:
    return "—" if _missing(x) else f"{num(x / 1000, 0)}{NBSP}k€"


def ratio(x, digits: int = 2) -> str:
    return num(x, digits)


def times(x, digits: int = 2) -> str:
    return "—" if _missing(x) else f"×{num(x, digits)}"


def date(x) -> str:
    """2020-03-23 -> 23 mars 2020."""
    if _missing(x):
        return "—"
    t = pd.Timestamp(x)
    return f"{t.day} {MONTHS[t.month - 1]} {t.year}"


def month(x) -> str:
    if _missing(x):
        return "—"
    t = pd.Timestamp(x)
    return f"{MONTHS[t.month - 1]} {t.year}"


def sessions(n) -> str:
    """Trading sessions with an approximate duration (21 sessions ≈ 1 month, 252 ≈ 1 year)."""
    if _missing(n):
        return "—"
    n = int(n)
    if n >= 252:
        return f"{n}{NBSP}séances (≈{NBSP}{num(n / 252, 1)}{NBSP}an{'s' if n >= 504 else ''})"
    return f"{n}{NBSP}séances (≈{NBSP}{num(n / 21, 0)}{NBSP}mois)"
