from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass
class PairInfo:
    pair: str
    token: str
    weth: str
    token_is_0: bool
    decimals: int
    symbol: str
    total_supply: int

    @property
    def scale(self) -> Decimal:
        return Decimal(10) ** self.decimals


@dataclass
class Market:
    eth_usd: Decimal
    price_eth: Decimal
    price_usd: Decimal
    liquidity_usd: Decimal
    market_cap_usd: Decimal
    reserve_token: Decimal
    reserve_eth: Decimal


@dataclass
class Buy:
    tx_hash: str
    block: int
    buyer: str
    eth_in: Decimal
    tokens_out: Decimal
    usd: Decimal
    price_usd: Decimal
    balance_before: Decimal
    balance_after: Decimal
    market: Market
    timestamp: int = 0
    router: str = ""
    swaps: int = 1
    is_new_holder: bool = field(init=False)
    position_pct: Decimal | None = field(init=False)

    def __post_init__(self) -> None:
        self.is_new_holder = self.balance_before <= 0
        self.position_pct = (
            (self.balance_after / self.balance_before - 1) * 100 if self.balance_before > 0 else None
        )
