from __future__ import annotations

import html
from decimal import Decimal

from .abi import to_checksum
from .format import fmt_amount, fmt_price, fmt_usd, short_addr
from .models import Buy
from .routers import router_name
from .state import State

CAPTION_LIMIT = 1024
TITLE_EMOJI = {"small": "🟢", "medium": "💚", "large": "🚀", "whale": "🐋"}
MEDALS = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]


def links_for(buy: Buy, token: str, pair: str, chain_slug: str = "ethereum") -> dict[str, str]:
    return {
        "tx": f"https://etherscan.io/tx/{buy.tx_hash}",
        "buyer": f"https://etherscan.io/address/{to_checksum(buy.buyer)}",
        "chart": f"https://dexscreener.com/{chain_slug}/{pair}",
        "dextools": f"https://www.dextools.io/app/en/ether/pair-explorer/{pair}",
        "buy": f"https://app.uniswap.org/swap?outputCurrency={to_checksum(token)}&chain=mainnet",
    }


def emoji_bar(usd: Decimal, st: State, budget_chars: int) -> str:
    s = st.settings
    n = max(1, int(usd / Decimal(str(s.emoji_step_usd)))) if s.emoji_step_usd > 0 else 1
    n = min(n, s.emoji_max)
    glyph = html.escape(s.emoji)
    if s.custom_emoji_id and s.custom_emoji_id.isdigit():
        unit = f'<tg-emoji emoji-id="{s.custom_emoji_id}">{glyph}</tg-emoji>'
        return unit * max(1, min(n, budget_chars // len(unit)))
    return glyph * max(1, min(n, budget_chars // max(1, len(glyph))))


def render_buy(buy: Buy, st: State, symbol: str, token: str, pair: str,
               flags: dict[str, bool], website: str) -> tuple[str, list[list[dict]]]:
    s = st.settings
    L = links_for(buy, token, pair)
    tier = st.tier_for(float(buy.usd))
    sym = html.escape(symbol)
    title = f"<b>🐋 WHALE {sym} BUY! 🐋</b>" if tier == "whale" else f"<b>{TITLE_EMOJI[tier]} {sym} BUY!</b>"

    lines = [
        f"💵 <b>Spent:</b> {fmt_amount(buy.eth_in, 4)} ETH <i>({fmt_usd(buy.usd)})</i>",
        f"🪙 <b>Got:</b> {fmt_amount(buy.tokens_out)} {sym}",
        f"👤 <b>Buyer:</b> <a href=\"{L['buyer']}\">{short_addr(buy.buyer)}</a> | <a href=\"{L['tx']}\">Txn</a>",
    ]
    if s.show_position:
        if buy.is_new_holder:
            lines.append("🆕 <b>New Holder!</b>")
        elif buy.position_pct is not None:
            lines.append(f"📈 <b>Position:</b> +{buy.position_pct:,.1f}%")
    if s.show_market:
        m = buy.market
        lines.append(f"📊 <b>Price:</b> {fmt_price(m.price_usd)}")
        lines.append(f"💧 <b>Liquidity:</b> {fmt_usd(m.liquidity_usd, 0)}")
        lines.append(f"🏦 <b>Market Cap:</b> {fmt_usd(m.market_cap_usd, 0)}")
    via = router_name(buy.router)
    if via:
        lines.append(f"🔀 <b>Via:</b> {html.escape(via)}")

    badges = []
    if flags.get("ath"):
        badges.append("🏆 <b>NEW ATH</b>")
    if flags.get("biggest_today"):
        badges.append("🔥 <b>Biggest buy today</b>")
    if st.streak >= 3:
        badges.append(f"⚡ <b>{st.streak} buy streak</b>")
    if badges:
        lines.append(" · ".join(badges))

    footer = f"<a href=\"{L['chart']}\">📈 Chart</a> | <a href=\"{L['buy']}\">🦄 Buy</a>"
    if website:
        footer += f" | <a href=\"{html.escape(website, quote=True)}\">🌐 Website</a>"
    for name, url in s.links.items():
        footer += f" | <a href=\"{html.escape(url, quote=True)}\">{html.escape(name)}</a>"

    fixed = f"{title}\n{{BAR}}\n\n" + "\n".join(lines) + f"\n\n{footer}"
    bar = emoji_bar(buy.usd, st, max(CAPTION_LIMIT - len(fixed) - 8, 1))
    text = fixed.replace("{BAR}", bar)

    keyboard = []
    if s.show_buttons:
        keyboard = [
            [{"text": f"🦄 Buy {symbol[:16]}", "url": L["buy"]}, {"text": "📈 Chart", "url": L["chart"]}],
            [{"text": "🔍 Txn", "url": L["tx"]}, {"text": "🧭 DEXTools", "url": L["dextools"]}],
        ]
    return text, keyboard


def render_stats(st: State, symbol: str, price_usd: Decimal, mcap: Decimal, liq: Decimal) -> str:
    st.roll_day()
    d = st.daily
    biggest = fmt_usd(d.biggest_usd)
    if d.biggest_tx:
        biggest += f" · <a href=\"https://etherscan.io/tx/{d.biggest_tx}\">Txn</a>"
    lines = [
        f"<b>📊 {html.escape(symbol)} today ({d.day} UTC)</b>",
        "",
        f"🛒 <b>Buys:</b> {d.buys}",
        f"💵 <b>Volume:</b> {fmt_usd(d.volume_usd)}",
        f"🆕 <b>New holders:</b> {d.new_holders}",
        f"🔥 <b>Biggest buy:</b> {biggest}",
        "",
        f"📊 <b>Price:</b> {fmt_price(price_usd)}",
        f"🏦 <b>Market Cap:</b> {fmt_usd(mcap, 0)}",
        f"💧 <b>Liquidity:</b> {fmt_usd(liq, 0)}",
        f"🏆 <b>ATH (tracked):</b> {fmt_price(Decimal(str(st.ath_price_usd)))}",
    ]
    board = st.leaderboard()
    if board:
        lines += ["", "<b>🥇 Top buyers today</b>"]
        for medal, (addr, usd) in zip(MEDALS, board):
            lines.append(f"{medal} <a href=\"https://etherscan.io/address/{to_checksum(addr)}\">"
                         f"{short_addr(addr)}</a> · {fmt_usd(usd)}")
    return "\n".join(lines)
