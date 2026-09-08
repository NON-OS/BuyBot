from __future__ import annotations

import html

from ..format import fmt_usd
from .limits import (
    BAR_RANGE,
    EMOJI_ID_RE,
    LINK_NAME_RE,
    MAX_EMOJI_CHARS,
    MAX_LINK_CHARS,
    MAX_LINKS,
    MIN_USD_RANGE,
    STEP_RANGE,
    TIER_RANGE,
)

TOGGLES = {"position": "show_position", "market": "show_market",
           "buttons": "show_buttons", "pinwhales": "pin_whales"}


class AppearanceCommands:
    async def cmd_setmin(self, args, reply, msg) -> str:
        lo, hi = MIN_USD_RANGE
        value = float(args[0])
        if not lo <= value <= hi:
            return f"Minimum must be between {fmt_usd(lo, 0)} and {fmt_usd(hi, 0)}."
        self.st.settings.min_usd = value
        return f"Minimum buy set to {fmt_usd(value)}."

    async def cmd_setstep(self, args, reply, msg) -> str:
        lo, hi = STEP_RANGE
        value = float(args[0])
        if not lo <= value <= hi:
            return f"Step must be between {fmt_usd(lo, 0)} and {fmt_usd(hi, 0)}."
        self.st.settings.emoji_step_usd = value
        return f"One emoji per {fmt_usd(value)}."

    async def cmd_setmax(self, args, reply, msg) -> str:
        lo, hi = BAR_RANGE
        value = int(args[0])
        if not lo <= value <= hi:
            return f"Max must be between {lo} and {hi}."
        self.st.settings.emoji_max = value
        return f"Emoji bar capped at {value}."

    async def cmd_settier(self, args, reply, msg) -> str:
        tier, usd = args[0].lower(), float(args[1])
        if tier not in ("medium", "large", "whale"):
            return "Tier must be medium, large or whale."
        lo, hi = TIER_RANGE
        if not lo <= usd <= hi:
            return f"Threshold must be between {fmt_usd(lo, 0)} and {fmt_usd(hi, 0)}."
        tiers = dict(self.st.settings.tier_usd)
        tiers[tier] = usd
        if not tiers["medium"] < tiers["large"] < tiers["whale"]:
            return "Thresholds must satisfy medium < large < whale."
        self.st.settings.tier_usd = tiers
        return (f"Tiers: medium from {fmt_usd(tiers['medium'])}, large from {fmt_usd(tiers['large'])}, "
                f"whale from {fmt_usd(tiers['whale'])}.")

    async def cmd_setemoji(self, args, reply, msg) -> str:
        settings = self.st.settings
        source = reply or msg
        custom = [e for e in source.get("entities", []) if e.get("type") == "custom_emoji"]
        if custom:
            entity = custom[0]
            emoji_id = str(entity.get("custom_emoji_id", ""))
            if not EMOJI_ID_RE.match(emoji_id):
                return "That custom emoji id looks invalid."
            text = source.get("text", "")
            glyph = text[entity["offset"]: entity["offset"] + entity["length"]]
            settings.custom_emoji_id = emoji_id
            settings.emoji = glyph if 0 < len(glyph) <= MAX_EMOJI_CHARS else "🟢"
            self.tg.custom_emoji_ok = True
            return (f"Premium emoji set (id <code>{emoji_id}</code>). Telegram renders custom emoji only "
                    "for bots that own a Fragment username, otherwise the standard emoji is used.")
        if args:
            glyph = args[0]
            if len(glyph) > MAX_EMOJI_CHARS or any(c in glyph for c in "<>&"):
                return "Send a single emoji."
            settings.emoji = glyph
            settings.custom_emoji_id = ""
            return f"Bar emoji set to {html.escape(glyph)}."
        return "Usage: /setemoji 🟢, or reply to a message containing a premium emoji."

    async def cmd_emojiid(self, args, reply, msg) -> str:
        source = reply or msg
        ids = [str(e.get("custom_emoji_id", "")) for e in source.get("entities", [])
               if e.get("type") == "custom_emoji"]
        ids = [i for i in ids if EMOJI_ID_RE.match(i)]
        if not ids:
            return "No premium emoji found in that message."
        return "Premium emoji ids:\n" + "\n".join(f"<code>{i}</code>" for i in ids)

    async def cmd_toggle(self, args, reply, msg) -> str:
        key = TOGGLES.get(args[0].lower() if args else "")
        if not key:
            return "Usage: /toggle position|market|buttons|pinwhales"
        setattr(self.st.settings, key, not getattr(self.st.settings, key))
        return f"{key} is now {'on' if getattr(self.st.settings, key) else 'off'}."

    async def cmd_addlink(self, args, reply, msg) -> str:
        if len(args) < 2:
            return "Usage: /addlink Name https://..."
        name, url = args[0], args[1]
        if not LINK_NAME_RE.match(name):
            return "Link name: up to 24 letters, digits or basic punctuation."
        if not url.lower().startswith(("https://", "http://", "tg://")) or len(url) > MAX_LINK_CHARS:
            return f"Link must be an http(s) or tg:// URL under {MAX_LINK_CHARS} characters."
        links = self.st.settings.links
        if name not in links and len(links) >= MAX_LINKS:
            return f"At most {MAX_LINKS} extra links."
        links[name] = url
        return f"Link added: {html.escape(name)}."

    async def cmd_dellink(self, args, reply, msg) -> str:
        if not args:
            return "Usage: /dellink Name"
        return "Link removed." if self.st.settings.links.pop(args[0], None) else "No such link."
