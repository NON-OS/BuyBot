from __future__ import annotations

import asyncio
import logging
import time
from decimal import Decimal

from .chain import Chain
from .config import Config
from .format import fmt_price, fmt_usd
from .models import Buy
from .poster import Poster
from .rpc import Rpc
from .state import State
from .swaps import TOPIC, Swaps
from .telegram import Telegram

log = logging.getLogger("buybot.watch")

MAX_BLOCKS_PER_SCAN = 2000
COALESCE_SECONDS = 0.25
# Never scan blocks older than this behind the head. The cursor scan only backs
# up the live WebSocket feed over brief gaps, so requesting older ranges buys
# nothing and, on a pruned public node, is rejected as an archive request. When
# the cursor falls further behind (a long outage), skip forward instead: the
# live feed carries current buys, and replaying an old range would stall here.
MAX_LOOKBACK_BLOCKS = 120


class Watcher:
    def __init__(self, cfg: Config, rpc: Rpc, tg: Telegram, state: State, chain: Chain,
                 swaps: Swaps, poster: Poster):
        self.cfg = cfg
        self.rpc = rpc
        self.tg = tg
        self.state = state
        self.chain = chain
        self.swaps = swaps
        self.poster = poster
        self._lock = asyncio.Lock()

    async def handle_buy(self, buy: Buy) -> bool:
        flags = self.state.record(buy.tx_hash, buy.buyer, float(buy.usd), buy.is_new_holder, float(buy.price_usd))
        if flags is None:
            return False
        if buy.usd < Decimal(str(self.state.settings.min_usd)):
            log.info("skip %s below minimum (%s)", buy.tx_hash, fmt_usd(buy.usd))
            return True
        if self.state.settings.paused:
            return True
        log.info("buy %s %s by %s tier=%s", buy.tx_hash, fmt_usd(buy.usd), buy.buyer, self.state.tier_for(float(buy.usd)))
        sent = await self.poster.post(buy, flags)
        if sent:
            self.state.mark_posted(buy.tx_hash, int(sent["message_id"]))
        return True

    async def handle_removed(self, tx_hash: str) -> None:
        message_id = self.state.forget(tx_hash)
        log.warning("reorg removed %s%s", tx_hash, " (deleting post)" if message_id else "")
        if message_id:
            await self.tg.delete(self.cfg.chat_id, message_id)

    def note_sells(self, count: int) -> None:
        if count:
            self.state.streak = 0

    async def fast_path(self) -> None:
        pending: list[dict] = []
        flush: asyncio.Task | None = None

        async def flush_later() -> None:
            await asyncio.sleep(COALESCE_SECONDS)
            batch, pending[:] = list(pending), []
            t0 = time.monotonic()
            try:
                self.note_sells(self.swaps.count_sells(batch))
                for buy in await self.swaps.from_logs(batch):
                    if await self.handle_buy(buy):
                        log.info("posted %s %.2fs after the log", buy.tx_hash, time.monotonic() - t0)
                self.state.save(self.cfg.state_file)
            except Exception as exc:
                log.error("fast path failed, cursor scan will retry: %s", exc)

        async for lg in self.rpc.subscribe_logs(self.cfg.pair, [TOPIC]):
            if lg.get("removed"):
                await self.handle_removed(lg.get("transactionHash", ""))
                continue
            pending.append(lg)
            if flush is None or flush.done():
                flush = asyncio.create_task(flush_later())

    async def scan_to(self, head: int) -> None:
        async with self._lock:
            target = head - self.cfg.confirmations
            if self.state.last_block == 0:
                self.state.last_block = target
                self.state.save(self.cfg.state_file)
                return
            if target <= self.state.last_block:
                return
            frm = self.state.last_block + 1
            floor = target - MAX_LOOKBACK_BLOCKS
            if frm < floor:
                log.warning("cursor %d is %d blocks behind head %d; skipping to %d, live feed covers the gap",
                            self.state.last_block, target - self.state.last_block, target, floor)
                frm = floor
            to = min(target, frm + MAX_BLOCKS_PER_SCAN - 1)
            buys = await self.swaps.in_range(frm, to)
            self.note_sells(self.swaps.last_sells)
            for buy in buys:
                if await self.handle_buy(buy):
                    await asyncio.sleep(0.3)
            self.state.last_block = to
            self.state.save(self.cfg.state_file)

    async def run(self) -> None:
        await self.chain.load()
        m = await self.chain.market()
        log.info("%s price %s mcap %s liq %s eth %s", self.poster.symbol, fmt_price(m.price_usd),
                 fmt_usd(m.market_cap_usd, 0), fmt_usd(m.liquidity_usd, 0), fmt_usd(m.eth_usd))
        await self._safe_scan(await self.rpc.block_number())
        if self.cfg.rpc_ws:
            log.info("realtime mode via %s", self.rpc.host())
            await asyncio.gather(self.fast_path(), self._heads_loop(), self._poll_loop(self.cfg.poll_seconds * 8))
        else:
            log.info("polling every %.1fs, set RPC_WS for instant posts", self.cfg.poll_seconds)
            await self._poll_loop(self.cfg.poll_seconds)

    async def _heads_loop(self) -> None:
        async for head in self.rpc.new_heads():
            await self._safe_scan(head)

    async def _poll_loop(self, interval: float) -> None:
        while True:
            try:
                await self._safe_scan(await self.rpc.block_number())
            except Exception as exc:
                log.error("poll: %s", exc)
            await asyncio.sleep(interval)

    async def _safe_scan(self, head: int) -> None:
        try:
            await self.scan_to(head)
        except Exception as exc:
            log.exception("scan failed at head %d: %s", head, exc)
            await asyncio.sleep(3)
