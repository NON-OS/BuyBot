from __future__ import annotations

import asyncio
from decimal import Decimal

from . import abi
from .chain import Chain
from .models import Buy

TOPIC = abi.TOPIC_SWAP


class Swaps:
    def __init__(self, chain: Chain):
        self.chain = chain
        self.rpc = chain.rpc
        self.last_sells = 0

    def _amounts(self, lg: dict):
        ws = abi.words(lg["data"])
        if lg.get("removed") or len(ws) < 4 or len(lg.get("topics", [])) < 3:
            return None
        info = self.chain.info
        a0in, a1in, a0out, a1out = ws[:4]
        if info.token_is_0:
            return a1in, a0out, a0in, a1out
        return a0in, a1out, a1in, a0out

    def count_sells(self, logs: list[dict]) -> int:
        n = 0
        for lg in logs:
            amounts = self._amounts(lg)
            if amounts and amounts[2] > 0 and amounts[3] > 0:
                n += 1
        return n

    async def in_range(self, from_block: int, to_block: int) -> list[Buy]:
        logs = await self.rpc.get_logs(self.chain.pair, [TOPIC], from_block, to_block)
        self.last_sells = self.count_sells(logs)
        return await self.from_logs(logs)

    async def from_logs(self, logs: list[dict]) -> list[Buy]:
        info = self.chain.info
        assert info
        per_tx: dict[str, dict] = {}
        for lg in logs:
            amounts = self._amounts(lg)
            if not amounts:
                continue
            eth_in, tok_out, _, _ = amounts
            if eth_in <= 0 or tok_out <= 0:
                continue
            entry = per_tx.setdefault(
                lg["transactionHash"],
                {"block": int(lg["blockNumber"], 16), "eth": 0, "tok": 0, "n": 0,
                 "to": abi.topic_to_address(lg["topics"][2])},
            )
            entry["eth"] += eth_in
            entry["tok"] += tok_out
            entry["n"] += 1
        if not per_tx:
            return []

        blocks = sorted({e["block"] for e in per_tx.values()})
        txs, blks, *mkts = await asyncio.gather(
            self.rpc.batch([("eth_getTransactionByHash", [h]) for h in per_tx]),
            self.rpc.batch([("eth_getBlockByNumber", [hex(b), False]) for b in blocks]),
            *[self.chain.market(b) for b in blocks],
        )
        markets = dict(zip(blocks, mkts))
        stamps = {b: (int(blk["timestamp"], 16) if blk else 0) for b, blk in zip(blocks, blks)}

        # the sender is the person; the log recipient would be the router
        rows = []
        for (tx_hash, entry), tx in zip(per_tx.items(), txs):
            tx = tx or {}
            rows.append((tx_hash, entry, (tx.get("from") or entry["to"]).lower(), (tx.get("to") or "").lower()))

        calls = []
        for _, entry, buyer, _ in rows:
            data = abi.encode_call(abi.SEL_BALANCE_OF, buyer)
            calls.append(("eth_call", [{"to": self.chain.token, "data": data}, hex(entry["block"] - 1)]))
            calls.append(("eth_call", [{"to": self.chain.token, "data": data}, hex(entry["block"])]))
        balances = await self.rpc.batch(calls)

        buys = []
        for i, (tx_hash, entry, buyer, router) in enumerate(rows):
            m = markets[entry["block"]]
            eth_in = Decimal(entry["eth"]) / Decimal(10**18)
            tokens = Decimal(entry["tok"]) / info.scale
            buys.append(
                Buy(
                    tx_hash=tx_hash,
                    block=entry["block"],
                    buyer=buyer,
                    eth_in=eth_in,
                    tokens_out=tokens,
                    usd=eth_in * m.eth_usd,
                    price_usd=(eth_in * m.eth_usd / tokens) if tokens else m.price_usd,
                    balance_before=Decimal(abi.decode_uint(balances[2 * i])) / info.scale,
                    balance_after=Decimal(abi.decode_uint(balances[2 * i + 1])) / info.scale,
                    market=m,
                    timestamp=stamps.get(entry["block"], 0),
                    router=router,
                    swaps=entry["n"],
                )
            )
        buys.sort(key=lambda b: (b.block, b.tx_hash))
        return buys
