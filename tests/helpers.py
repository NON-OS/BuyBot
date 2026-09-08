from decimal import Decimal

from buybot.models import Buy, Market


def market(eth_usd="4300", price_usd="0.002734") -> Market:
    return Market(
        eth_usd=Decimal(eth_usd),
        price_eth=Decimal("0.00000063"),
        price_usd=Decimal(price_usd),
        liquidity_usd=Decimal("170919"),
        market_cap_usd=Decimal("2169410"),
        reserve_token=Decimal("31000000"),
        reserve_eth=Decimal("19.9"),
    )


def buy(usd, before="0", router="0x1111111254eeb25477b68fb85ed929f73a960582") -> Buy:
    m = market()
    eth = Decimal(str(usd)) / m.eth_usd
    tokens = eth / m.price_eth
    return Buy(
        tx_hash="0x" + "cd" * 32,
        block=21_000_000,
        buyer="0x5aaeb6053f3e94c9b9a09f33669435e7ef1beaed",
        eth_in=eth,
        tokens_out=tokens,
        usd=Decimal(str(usd)),
        price_usd=m.price_usd,
        balance_before=Decimal(before),
        balance_after=Decimal(before) + tokens,
        market=m,
        router=router,
    )


def word(v: int) -> str:
    return hex(v)[2:].rjust(64, "0")
