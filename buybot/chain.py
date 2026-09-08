from __future__ import annotations

import logging
from decimal import Decimal, getcontext

from . import abi
from .models import Market, PairInfo
from .rpc import Rpc

log = logging.getLogger("buybot.chain")

# raw uint256 amounts do not fit the default 28 significant digits
getcontext().prec = 60

ZERO = "0x0000000000000000000000000000000000000000"
DEAD = "0x000000000000000000000000000000000000dead"


class Chain:
    def __init__(self, rpc: Rpc, token: str, pair: str, weth: str, eth_usd_feed: str, fallback_symbol: str):
        self.rpc = rpc
        self.token = token.lower()
        self.pair = pair.lower()
        self.weth = weth.lower()
        self.feed = eth_usd_feed
        self.fallback_symbol = fallback_symbol
        self.info: PairInfo | None = None

    async def load(self) -> PairInfo:
        t0, dec, sym, supply = await self.rpc.batch(
            [
                ("eth_call", [{"to": self.pair, "data": abi.SEL_TOKEN0}, "latest"]),
                ("eth_call", [{"to": self.token, "data": abi.SEL_DECIMALS}, "latest"]),
                ("eth_call", [{"to": self.token, "data": abi.SEL_SYMBOL}, "latest"]),
                ("eth_call", [{"to": self.token, "data": abi.SEL_TOTAL_SUPPLY}, "latest"]),
            ]
        )
        self.info = PairInfo(
            pair=self.pair,
            token=self.token,
            weth=self.weth,
            token_is_0=abi.decode_address(t0) == self.token,
            decimals=abi.decode_uint(dec) or 18,
            symbol=abi.decode_string(sym) or self.fallback_symbol,
            total_supply=abi.decode_uint(supply),
        )
        log.info("pair %s: %s is token%d, %d decimals", self.pair, self.info.symbol,
                 0 if self.info.token_is_0 else 1, self.info.decimals)
        return self.info

    async def market(self, block: int | str = "latest") -> Market:
        assert self.info
        tag = block if isinstance(block, str) else hex(block)
        reserves, round_data, supply, dead, zero = await self.rpc.batch(
            [
                ("eth_call", [{"to": self.pair, "data": abi.SEL_GET_RESERVES}, tag]),
                ("eth_call", [{"to": self.feed, "data": abi.SEL_LATEST_ROUND}, tag]),
                ("eth_call", [{"to": self.token, "data": abi.SEL_TOTAL_SUPPLY}, tag]),
                ("eth_call", [{"to": self.token, "data": abi.encode_call(abi.SEL_BALANCE_OF, DEAD)}, tag]),
                ("eth_call", [{"to": self.token, "data": abi.encode_call(abi.SEL_BALANCE_OF, ZERO)}, tag]),
            ]
        )
        r0, r1 = abi.words(reserves)[:2]
        r_tok, r_eth = (r0, r1) if self.info.token_is_0 else (r1, r0)
        eth_usd = Decimal(abi.words(round_data)[1]) / Decimal(10**8)
        reserve_token = Decimal(r_tok) / self.info.scale
        reserve_eth = Decimal(r_eth) / Decimal(10**18)
        price_eth = reserve_eth / reserve_token if reserve_token else Decimal(0)
        price_usd = price_eth * eth_usd
        circulating = abi.decode_uint(supply) - abi.decode_uint(dead) - abi.decode_uint(zero)
        return Market(
            eth_usd=eth_usd,
            price_eth=price_eth,
            price_usd=price_usd,
            liquidity_usd=reserve_eth * eth_usd * 2,
            market_cap_usd=Decimal(max(circulating, 0)) / self.info.scale * price_usd,
            reserve_token=reserve_token,
            reserve_eth=reserve_eth,
        )
