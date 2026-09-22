import unittest
from decimal import Decimal

from buybot.render import CAPTION_LIMIT, render_buy, render_stats
from buybot.state import State
from buybot.telegram import TG_EMOJI_RE
from tests.helpers import buy

TOKEN = "0x0a26c80Be4E060e688d7C23aDdB92cBb5D2C9eCA"
PAIR = "0x07CE5889D2EB681Af3bD61db24Ab2602c502Bd1B"


def render(b, st, flags=None, website="https://nonos.software"):
    return render_buy(b, st, "NOX", TOKEN, PAIR, flags or {}, website)


class BuyMessageTests(unittest.TestCase):
    def test_new_holder_and_router(self):
        text, keyboard = render(buy(500), State())
        self.assertIn("New Holder", text)
        self.assertIn("1inch", text)
        self.assertIn("0x5aAe…eAed", text)
        self.assertEqual(len(keyboard), 2)

    def test_existing_holder_shows_position(self):
        text, _ = render(buy(500, before="1000"), State())
        self.assertIn("Position:</b> +", text)
        self.assertNotIn("New Holder", text)

    def test_emoji_slot_override_uses_custom_with_fallback(self):
        st = State()
        st.settings.emojis["spent"] = "5111111111111111111"
        text, _ = render(buy(500), st)
        self.assertIn('<tg-emoji emoji-id="5111111111111111111">💵</tg-emoji>', text)
        stripped = TG_EMOJI_RE.sub(r"\1", text)
        self.assertIn("💵", stripped)
        self.assertNotIn("tg-emoji", stripped)

    def test_unset_slots_use_standard_emoji(self):
        text, _ = render(buy(500), State())
        self.assertIn("💵", text)
        self.assertNotIn("tg-emoji", text)

    def test_unknown_router_is_omitted(self):
        text, _ = render(buy(500, router="0x00000000000000000000000000000000deadbeef"), State())
        self.assertNotIn("Via:", text)

    def test_caption_fits_with_custom_emoji_and_badges(self):
        st = State()
        st.settings.custom_emoji_id = "5368324170671202286"
        st.settings.emoji_max = 200
        st.settings.links = {"Trending": "https://t.me/x", "Docs": "https://docs.example"}
        st.streak = 12
        text, _ = render(buy(50000), st, {"ath": True, "biggest_today": True})
        self.assertLessEqual(len(text), CAPTION_LIMIT)
        self.assertIn("WHALE", text)
        self.assertIn("NEW ATH", text)
        self.assertIn("12 buy streak", text)
        stripped = TG_EMOJI_RE.sub(r"\1", text)
        self.assertNotIn("tg-emoji", stripped)
        self.assertIn("🟢🟢", stripped)

    def test_bar_scales_with_size(self):
        st = State()
        small, _ = render(buy(30), st)
        big, _ = render(buy(600), st)
        self.assertEqual(small.count("🟢") - 1, 1)
        self.assertEqual(big.count("🟢"), 24)

    def test_hostile_settings_are_escaped(self):
        st = State()
        st.settings.emoji = "<b>x</b>"
        st.settings.links = {"Ev<il": 'https://x/"onmouseover=1'}
        text, _ = render(buy(100), st)
        self.assertNotIn("<b>x</b>", text)
        self.assertIn("&lt;b&gt;x&lt;/b&gt;", text)
        self.assertIn("Ev&lt;il", text)
        self.assertNotIn('"onmouseover=1"', text)

    def test_non_numeric_emoji_id_is_not_emitted(self):
        st = State()
        st.settings.custom_emoji_id = "abc"
        text, _ = render(buy(100), st)
        self.assertNotIn("tg-emoji", text)

    def test_market_and_buttons_can_be_hidden(self):
        st = State()
        st.settings.show_market = False
        st.settings.show_buttons = False
        text, keyboard = render(buy(100), st)
        self.assertNotIn("Liquidity", text)
        self.assertEqual(keyboard, [])


class StatsTests(unittest.TestCase):
    def test_leaderboard(self):
        st = State()
        st.record("0x1", "0x5aaeb6053f3e94c9b9a09f33669435e7ef1beaed", 1200, True, 0.0027)
        out = render_stats(st, "NOX", Decimal("0.0027"), Decimal("2000000"), Decimal("170000"))
        self.assertIn("Top buyers", out)
        self.assertIn("$1,200.00", out)
        self.assertIn("0x5aAe…eAed", out)
