from __future__ import annotations

from decimal import Decimal

from .abi import to_checksum

SUBSCRIPT = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")


def fmt_usd(v: Decimal | float, decimals: int = 2) -> str:
    v = Decimal(str(v))
    if v >= 1_000_000_000:
        return f"${v / 1_000_000_000:,.2f}B"
    if v >= 1_000_000:
        return f"${v / 1_000_000:,.2f}M"
    return f"${v:,.{decimals}f}"


def fmt_amount(v: Decimal, max_decimals: int = 2) -> str:
    if v >= 1_000_000_000:
        return f"{v / 1_000_000_000:,.2f}B"
    if v >= 1_000_000:
        return f"{v / 1_000_000:,.2f}M"
    if v >= 10_000:
        return f"{v:,.0f}"
    if v >= 1:
        return f"{v:,.{max_decimals}f}"
    return f"{v:.4f}".rstrip("0").rstrip(".") or "0"


def fmt_price(p: Decimal, sig: int = 4) -> str:
    if p <= 0:
        return "$0"
    if p >= 1:
        return f"${p:,.4f}".rstrip("0").rstrip(".")
    frac = f"{p:.30f}".split(".")[1]
    zeros = len(frac) - len(frac.lstrip("0"))
    digits = frac[zeros: zeros + sig].rstrip("0") or "0"
    if zeros >= 4:
        return f"$0.0{str(zeros).translate(SUBSCRIPT)}{digits}"
    return f"$0.{'0' * zeros}{digits}"


def short_addr(a: str) -> str:
    c = to_checksum(a)
    return f"{c[:6]}…{c[-4:]}"
