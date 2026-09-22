from __future__ import annotations

import time

from .chain import Chain
from .format import fmt_usd
from .render import render_stats
from .rpc import Rpc
from .state import State
from .telegram import Telegram


class Reporter:
    def __init__(self, rpc: Rpc, tg: Telegram, state: State, chain: Chain, symbol_of):
        self.rpc = rpc
        self.tg = tg
        self.state = state
        self.chain = chain
        self.symbol_of = symbol_of
        self.started = time.time()

    async def status(self) -> str:
        s = self.state.settings
        head = await self.rpc.block_number()
        up = int(time.time() - self.started)
        media = ", ".join(f"{t}:{self.state.media[t]['kind']}" for t in self.state.media) or "bundled defaults"
        custom = f" (custom {s.custom_emoji_id})" if s.custom_emoji_id else ""
        slots = sum(1 for v in s.emojis.values() if v.isdigit())
        return (
            "<b>NOX buybot</b>\n"
            f"Uptime {up // 3600}h {(up % 3600) // 60}m, head {head}, cursor {self.state.last_block}, "
            f"lag {max(0, head - self.state.last_block)} blocks\n"
            f"Posting: {'paused' if s.paused else 'live'}. Buys posted: {self.state.total_buys}\n"
            f"Min {fmt_usd(s.min_usd)}, step {fmt_usd(s.emoji_step_usd)}, max {s.emoji_max}, emoji {s.emoji}{custom}\n"
            f"Tiers: medium {fmt_usd(s.tier_usd['medium'])}, large {fmt_usd(s.tier_usd['large'])}, "
            f"whale {fmt_usd(s.tier_usd['whale'])}\n"
            f"Media: {media}\n"
            f"Custom emoji: {'on' if self.tg.custom_emoji_ok else 'off (standard emoji shown)'}, {slots} slot(s) set\n"
            f"RPC {self.rpc.host()}, log span {self.rpc.max_log_span}, batch {self.rpc.batch_size}"
        )

    async def stats(self) -> str:
        m = await self.chain.market()
        return render_stats(self.state, self.symbol_of(), m.price_usd, m.market_cap_usd, m.liquidity_usd)
