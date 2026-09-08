import tempfile
import unittest
from decimal import Decimal
from pathlib import Path

from buybot.config import Config
from buybot.state import State
from buybot.watcher import Watcher
from tests.helpers import buy

CHAT = -1001234567890


class FakeTelegram:
    def __init__(self):
        self.deleted = []

    async def delete(self, chat_id, message_id):
        self.deleted.append((chat_id, message_id))
        return True


class FakePoster:
    def __init__(self):
        self.posted = []
        self.next_id = 100

    @property
    def symbol(self):
        return "NOX"

    async def post(self, b, flags):
        self.posted.append((b.tx_hash, flags))
        self.next_id += 1
        return {"message_id": self.next_id}


def make_watcher(tmp: Path):
    cfg = Config(
        bot_token="1:x", chat_id=CHAT, rpc_http="http://node.invalid", rpc_ws="",
        state_file=tmp / "state.json", media_dir=tmp,
    )
    state = State()
    tg = FakeTelegram()
    poster = FakePoster()
    watcher = Watcher(cfg, rpc=None, tg=tg, state=state, chain=None, swaps=None, poster=poster)
    return watcher, state, tg, poster


class HandleBuyTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.watcher, self.state, self.tg, self.poster = make_watcher(Path(self.dir.name))

    def tearDown(self):
        self.dir.cleanup()

    async def test_posts_once_per_transaction(self):
        b = buy(500)
        self.assertTrue(await self.watcher.handle_buy(b))
        self.assertFalse(await self.watcher.handle_buy(b))
        self.assertEqual(len(self.poster.posted), 1)
        self.assertEqual(self.state.posted[b.tx_hash], 101)

    async def test_below_minimum_is_counted_but_not_posted(self):
        self.state.settings.min_usd = 100
        self.assertTrue(await self.watcher.handle_buy(buy(10)))
        self.assertEqual(self.poster.posted, [])
        self.assertEqual(self.state.daily.buys, 1)

    async def test_paused_suppresses_posting(self):
        self.state.settings.paused = True
        await self.watcher.handle_buy(buy(500))
        self.assertEqual(self.poster.posted, [])

    async def test_reorg_deletes_the_message(self):
        b = buy(500)
        await self.watcher.handle_buy(b)
        await self.watcher.handle_removed(b.tx_hash)
        self.assertEqual(self.tg.deleted, [(CHAT, 101)])
        self.assertEqual(self.state.total_buys, 0)
        self.assertTrue(await self.watcher.handle_buy(b))

    async def test_reorg_of_unposted_transaction_is_harmless(self):
        await self.watcher.handle_removed("0xnever-seen")
        self.assertEqual(self.tg.deleted, [])

    async def test_sells_reset_the_streak(self):
        await self.watcher.handle_buy(buy(500))
        self.assertEqual(self.state.streak, 1)
        self.watcher.note_sells(1)
        self.assertEqual(self.state.streak, 0)
        self.watcher.note_sells(0)
        self.assertEqual(self.state.streak, 0)

    async def test_ath_badge_only_after_a_first_price(self):
        first = buy(100)
        await self.watcher.handle_buy(first)
        self.assertFalse(self.poster.posted[0][1]["ath"])
        higher = buy(200)
        higher.tx_hash = "0x" + "ef" * 32
        higher.price_usd = Decimal("0.9")
        await self.watcher.handle_buy(higher)
        self.assertTrue(self.poster.posted[1][1]["ath"])
