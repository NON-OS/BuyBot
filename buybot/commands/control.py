from __future__ import annotations

import time

from ..media import media_from_message
from ..state import TIERS
from .limits import TEST_COOLDOWN, TEST_RANGE


class ControlCommands:
    async def cmd_status(self, args, reply, msg) -> str:
        return await self.status_text()

    async def cmd_stats(self, args, reply, msg) -> str:
        return await self.stats_text()

    async def cmd_leaderboard(self, args, reply, msg) -> str:
        return await self.stats_text()

    async def cmd_test(self, args, reply, msg) -> str | None:
        now = time.time()
        waited = now - self._last_test
        if waited < TEST_COOLDOWN:
            return f"Wait {int(TEST_COOLDOWN - waited) + 1}s between test posts."
        lo, hi = TEST_RANGE
        usd = float(args[0]) if args else 500.0
        if not lo <= usd <= hi:
            return f"Test size must be between ${lo:,.0f} and ${hi:,.0f}."
        self._last_test = now
        await self.post_test(usd)
        return None

    async def cmd_pause(self, args, reply, msg) -> str:
        self.st.settings.paused = True
        return "Paused. Buys are still tracked, not posted."

    async def cmd_resume(self, args, reply, msg) -> str:
        self.st.settings.paused = False
        return "Resumed."

    async def cmd_setmedia(self, args, reply, msg) -> str:
        if not reply:
            return "Reply to a GIF, MP4, photo or sticker with /setmedia <tier|all>."
        found = media_from_message(reply)
        if not found:
            return "That message has no supported media."
        kind, file_id = found
        target = args[0].lower() if args else "all"
        tiers = list(TIERS) if target == "all" else [target]
        if any(t not in TIERS for t in tiers):
            return f"Tier must be one of {', '.join(TIERS)} or all."
        for tier in tiers:
            self.st.media[tier] = {"kind": kind, "file_id": file_id}
        return f"Media ({kind}) set for: {', '.join(tiers)}."

    async def cmd_clearmedia(self, args, reply, msg) -> str:
        target = args[0].lower() if args else "all"
        if target != "all" and target not in TIERS:
            return f"Tier must be one of {', '.join(TIERS)} or all."
        for tier in (TIERS if target == "all" else [target]):
            self.st.media.pop(tier, None)
        return "Media cleared, the bundled animations are used again."
