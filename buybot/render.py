from __future__ import annotations

import html
from decimal import Decimal

from .abi import to_checksum
from .format import fmt_amount, fmt_price, fmt_usd, short_addr
from .models import Buy
from .routers import router_name
from .state import State

CAPTION_LIMIT = 1024

# Every emoji in a message comes from one of these named slots. The value here
# is the standard emoji shown by default; a slot can be pointed at a chosen
# emoji from the group's emoji settings (Settings.emojis[slot] = id), and when
# that emoji cannot be shown the standard one below is used instead.
DEFAULT_EMOJI: dict[str, str] = {
    # buy title, by size tier
    "small": "🟢", "medium": "💚", "large": "🚀", "whale": "🐋",
    # buy body
    "spent": "💵", "got": "🪙", "buyer": "👤", "position": "📈", "new": "🆕",
    "price": "📊", "liquidity": "💧", "mcap": "🏦", "via": "🔀",
    # badges
    "ath": "🏆", "fire": "🔥", "streak": "⚡",
    # footer / buttons
    "chart": "📈", "buy": "🦄", "web": "🌐", "txn": "🔍", "dextools": "🧭",
    # stats card
    "buys": "🛒", "volume": "💵", "holders": "🆕", "biggest": "🔥", "board": "🥇",
    "m1": "🥇", "m2": "🥈", "m3": "🥉", "m4": "4️⃣", "m5": "5️⃣",
}
MEDAL_SLOTS = ["m1", "m2", "m3", "m4", "m5"]


def em(st: State, slot: str) -> str:
    """The emoji for a slot: the chosen one from emoji settings wrapped so a
    standard emoji shows wherever the chosen one cannot, else the standard one."""
    fallback = DEFAULT_EMOJI.get(slot, "")
    emoji_id = st.settings.emojis.get(slot, "")
    if emoji_id.isdigit():
        return f'<tg-emoji emoji-id="{emoji_id}">{html.escape(fallback)}</tg-emoji>'
    return html.escape(fallback)


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
    emoji_id = s.emojis.get("bar", s.custom_emoji_id)
    if emoji_id and emoji_id.isdigit():
        unit = f'<tg-emoji emoji-id="{emoji_id}">{glyph}</tg-emoji>'
        return unit * max(1, min(n, budget_chars // len(unit)))
    return glyph * max(1, min(n, budget_chars // max(1, len(glyph))))


def render_buy(buy: Buy, st: State, symbol: str, token: str, pair: str,
               flags: dict[str, bool], website: str) -> tuple[str, list[list[dict]]]:
    s = st.settings
    L = links_for(buy, token, pair)
    tier = st.tier_for(float(buy.usd))
    sym = html.escape(symbol)
    if tier == "whale":
        whale = em(st, "whale")
        title = f"<b>{whale} WHALE {sym} BUY! {whale}</b>"
    else:
        title = f"<b>{em(st, tier)} {sym} BUY!</b>"

    lines = [
        f"{em(st, 'spent')} <b>Spent:</b> {fmt_amount(buy.eth_in, 4)} ETH <i>({fmt_usd(buy.usd)})</i>",
        f"{em(st, 'got')} <b>Got:</b> {fmt_amount(buy.tokens_out)} {sym}",
        f"{em(st, 'buyer')} <b>Buyer:</b> <a href=\"{L['buyer']}\">{short_addr(buy.buyer)}</a>"
        f" | <a href=\"{L['tx']}\">Txn</a>",
    ]
    if s.show_position:
        if buy.is_new_holder:
            lines.append(f"{em(st, 'new')} <b>New Holder!</b>")
        elif buy.position_pct is not None:
            lines.append(f"{em(st, 'position')} <b>Position:</b> +{buy.position_pct:,.1f}%")
    if s.show_market:
        m = buy.market
        lines.append(f"{em(st, 'price')} <b>Price:</b> {fmt_price(m.price_usd)}")
        lines.append(f"{em(st, 'liquidity')} <b>Liquidity:</b> {fmt_usd(m.liquidity_usd, 0)}")
        lines.append(f"{em(st, 'mcap')} <b>Market Cap:</b> {fmt_usd(m.market_cap_usd, 0)}")
    via = router_name(buy.router)
    if via:
        lines.append(f"{em(st, 'via')} <b>Via:</b> {html.escape(via)}")

    badges = []
    if flags.get("ath"):
        badges.append(f"{em(st, 'ath')} <b>NEW ATH</b>")
    if flags.get("biggest_today"):
        badges.append(f"{em(st, 'fire')} <b>Biggest buy today</b>")
    if st.streak >= 3:
        badges.append(f"{em(st, 'streak')} <b>{st.streak} buy streak</b>")
    if badges:
        lines.append(" · ".join(badges))

    footer = (f"<a href=\"{L['chart']}\">{em(st, 'chart')} Chart</a>"
              f" | <a href=\"{L['buy']}\">{em(st, 'buy')} Buy</a>")
    if website:
        footer += f" | <a href=\"{html.escape(website, quote=True)}\">{em(st, 'web')} Website</a>"
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
        f"<b>{em(st, 'price')} {html.escape(symbol)} today ({d.day} UTC)</b>",
        "",
        f"{em(st, 'buys')} <b>Buys:</b> {d.buys}",
        f"{em(st, 'volume')} <b>Volume:</b> {fmt_usd(d.volume_usd)}",
        f"{em(st, 'holders')} <b>New holders:</b> {d.new_holders}",
        f"{em(st, 'biggest')} <b>Biggest buy:</b> {biggest}",
        "",
        f"{em(st, 'price')} <b>Price:</b> {fmt_price(price_usd)}",
        f"{em(st, 'mcap')} <b>Market Cap:</b> {fmt_usd(mcap, 0)}",
        f"{em(st, 'liquidity')} <b>Liquidity:</b> {fmt_usd(liq, 0)}",
        f"{em(st, 'ath')} <b>ATH (tracked):</b> {fmt_price(Decimal(str(st.ath_price_usd)))}",
    ]
    board = st.leaderboard()
    if board:
        lines += ["", f"<b>{em(st, 'board')} Top buyers today</b>"]
        for slot, (addr, usd) in zip(MEDAL_SLOTS, board):
            lines.append(f"{em(st, slot)} <a href=\"https://etherscan.io/address/{to_checksum(addr)}\">"
                         f"{short_addr(addr)}</a> · {fmt_usd(usd)}")
    return "\n".join(lines)
