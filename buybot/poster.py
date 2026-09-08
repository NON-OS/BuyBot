from __future__ import annotations

import logging
from decimal import Decimal
from pathlib import Path

from .chain import Chain
from .config import Config
from .media import media_kind_for
from .models import Buy
from .render import render_buy
from .state import State
from .telegram import Telegram, TelegramError

log = logging.getLogger("buybot.post")

DEFAULT_MEDIA = {
    "small": ["buy-small.mp4", "buy-small.gif", "nox-badge.png"],
    "medium": ["buy-medium.mp4", "buy-medium.gif", "nox-badge.png"],
    "large": ["buy-large.mp4", "buy-large.gif", "nox-badge.png"],
    "whale": ["buy-whale.mp4", "buy-whale.gif", "nox-badge.png"],
}
SAMPLE_ROUTER = "0x3fc91a3afd70395cd496c647d5a6cc9d4b2b7fad"


class Poster:
    def __init__(self, cfg: Config, tg: Telegram, state: State, chain: Chain):
        self.cfg = cfg
        self.tg = tg
        self.state = state
        self.chain = chain

    @property
    def symbol(self) -> str:
        return self.chain.info.symbol if self.chain.info else self.cfg.symbol

    def media_for(self, tier: str) -> tuple[str, object] | None:
        entry = self.state.media.get(tier)
        if entry:
            return entry["kind"], entry["file_id"]
        for name in DEFAULT_MEDIA[tier]:
            path = self.cfg.media_dir / name
            if path.is_file():
                return media_kind_for(path), path
        return None

    async def post(self, buy: Buy, flags: dict[str, bool]) -> dict | None:
        text, keyboard = render_buy(buy, self.state, self.symbol, self.cfg.token, self.cfg.pair, flags, self.cfg.website)
        tier = self.state.tier_for(float(buy.usd))
        media = self.media_for(tier)
        try:
            if media:
                kind, ref = media
                sent = await self.tg.send_media(self.cfg.chat_id, kind, ref, text, keyboard)
                if isinstance(ref, Path) and kind in sent:
                    file_id = sent["photo"][-1]["file_id"] if kind == "photo" else sent[kind]["file_id"]
                    self.state.media[tier] = {"kind": kind, "file_id": file_id}
            else:
                sent = await self.tg.send_text(self.cfg.chat_id, text, keyboard)
        except TelegramError as exc:
            log.error("post failed for %s: %s", buy.tx_hash, exc)
            if not media or exc.code != 400:
                return None
            self.state.media.pop(tier, None)
            try:
                sent = await self.tg.send_text(self.cfg.chat_id, text, keyboard)
            except TelegramError as exc2:
                log.error("text fallback failed for %s: %s", buy.tx_hash, exc2)
                return None
        if tier == "whale" and self.state.settings.pin_whales:
            await self.tg.pin(self.cfg.chat_id, sent["message_id"])
        return sent

    async def post_sample(self, usd: float) -> None:
        m = await self.chain.market()
        eth = Decimal(str(usd)) / m.eth_usd if m.eth_usd else Decimal(0)
        tokens = eth / m.price_eth if m.price_eth else Decimal(0)
        buy = Buy(
            tx_hash="0x" + "ab" * 32, block=0, buyer=self.cfg.token.lower(),
            eth_in=eth, tokens_out=tokens, usd=Decimal(str(usd)), price_usd=m.price_usd,
            balance_before=Decimal(0), balance_after=tokens, market=m, router=SAMPLE_ROUTER,
        )
        await self.post(buy, {"ath": False, "biggest_today": False})
