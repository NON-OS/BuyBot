"""Scan cursor, admin settings, media ids and the daily counters."""
from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import Any, TypeVar

log = logging.getLogger("buybot.state")

T = TypeVar("T")

TIERS = ("small", "medium", "large", "whale")


def _merge(cls: type, raw: Any) -> Any:
    """Keeps only the fields the dataclass declares, so a hand-edited or
    older state file cannot break startup."""
    if not isinstance(raw, dict):
        return cls()
    known = {f.name for f in fields(cls)}
    return cls(**{**asdict(cls()), **{k: v for k, v in raw.items() if k in known}})


@dataclass
class Settings:
    min_usd: float = 25.0
    emoji: str = "🟢"
    emoji_step_usd: float = 25.0
    emoji_max: int = 60
    custom_emoji_id: str = ""
    # Per-slot emoji overrides: slot name -> custom emoji id. A slot left unset
    # falls back to the standard emoji baked into the message.
    emojis: dict[str, str] = field(default_factory=dict)
    tier_usd: dict[str, float] = field(default_factory=lambda: {"medium": 250.0, "large": 1000.0, "whale": 5000.0})
    show_position: bool = True
    show_market: bool = True
    show_buttons: bool = True
    pin_whales: bool = False
    paused: bool = False
    links: dict[str, str] = field(default_factory=dict)


@dataclass
class Daily:
    day: str = ""
    buys: int = 0
    volume_usd: float = 0.0
    biggest_usd: float = 0.0
    biggest_tx: str = ""
    new_holders: int = 0
    buyers: dict[str, float] = field(default_factory=dict)


@dataclass
class State:
    last_block: int = 0
    settings: Settings = field(default_factory=Settings)
    media: dict[str, dict[str, str]] = field(default_factory=dict)
    daily: Daily = field(default_factory=Daily)
    ath_price_usd: float = 0.0
    seen_tx: list[str] = field(default_factory=list)
    posted: dict[str, int] = field(default_factory=dict)
    streak: int = 0
    total_buys: int = 0

    @classmethod
    def load(cls, path: Path) -> State:
        if not path.exists():
            return cls()
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            log.error("unreadable state file %s (%s); starting fresh", path, exc)
            return cls()
        if not isinstance(raw, dict):
            return cls()
        st = cls()
        st.last_block = int(raw.get("last_block", 0))
        st.settings = _merge(Settings, raw.get("settings"))
        st.media = raw.get("media", {})
        st.daily = _merge(Daily, raw.get("daily"))
        st.ath_price_usd = float(raw.get("ath_price_usd", 0.0))
        st.seen_tx = list(raw.get("seen_tx", []))[-500:]
        st.posted = {str(k): int(v) for k, v in dict(raw.get("posted", {})).items()}
        st.streak = int(raw.get("streak", 0))
        st.total_buys = int(raw.get("total_buys", 0))
        return st

    def save(self, path: Path) -> None:
        tmp = path.with_suffix(".tmp")
        data: dict[str, Any] = {
            "last_block": self.last_block,
            "settings": asdict(self.settings),
            "media": self.media,
            "daily": asdict(self.daily),
            "ath_price_usd": self.ath_price_usd,
            "seen_tx": self.seen_tx[-500:],
            "posted": dict(list(self.posted.items())[-200:]),
            "streak": self.streak,
            "total_buys": self.total_buys,
        }
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2)
        tmp.replace(path)

    def tier_for(self, usd: float) -> str:
        t = self.settings.tier_usd
        if usd >= t.get("whale", 5000):
            return "whale"
        if usd >= t.get("large", 1000):
            return "large"
        if usd >= t.get("medium", 250):
            return "medium"
        return "small"

    def roll_day(self) -> None:
        today = time.strftime("%Y-%m-%d", time.gmtime())
        if self.daily.day != today:
            self.daily = Daily(day=today)

    def record(self, tx_hash: str, buyer: str, usd: float, new_holder: bool, price_usd: float) -> dict[str, bool] | None:
        """Returns the badge flags, or None when this transaction was already handled."""
        self.roll_day()
        flags = {"ath": False, "biggest_today": False}
        if tx_hash in self.seen_tx:
            return None
        self.seen_tx.append(tx_hash)
        self.seen_tx = self.seen_tx[-500:]
        d = self.daily
        d.buys += 1
        d.volume_usd += usd
        if new_holder:
            d.new_holders += 1
        if usd > d.biggest_usd:
            flags["biggest_today"] = d.buys > 1
            d.biggest_usd, d.biggest_tx = usd, tx_hash
        d.buyers[buyer] = d.buyers.get(buyer, 0.0) + usd
        if price_usd > self.ath_price_usd:
            flags["ath"] = self.ath_price_usd > 0
            self.ath_price_usd = price_usd
        self.streak += 1
        self.total_buys += 1
        return flags

    def mark_posted(self, tx_hash: str, message_id: int) -> None:
        self.posted[tx_hash] = message_id
        if len(self.posted) > 200:
            for key in list(self.posted)[: len(self.posted) - 200]:
                del self.posted[key]

    def forget(self, tx_hash: str) -> int | None:
        """Undoes a reorged buy and returns its message id, if it was posted."""
        if tx_hash in self.seen_tx:
            self.seen_tx.remove(tx_hash)
            self.total_buys = max(0, self.total_buys - 1)
            self.daily.buys = max(0, self.daily.buys - 1)
        return self.posted.pop(tx_hash, None)

    def leaderboard(self, n: int = 5) -> list[tuple[str, float]]:
        return sorted(self.daily.buyers.items(), key=lambda kv: kv[1], reverse=True)[:n]
