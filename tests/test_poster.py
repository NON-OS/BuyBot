import tempfile
import unittest
from pathlib import Path

from buybot.config import Config
from buybot.models import PairInfo
from buybot.poster import Poster
from buybot.state import State
from buybot.telegram import TelegramError
from tests.helpers import buy

CHAT = -1001234567890


class FakeTelegram:
    def __init__(self, media_error=None):
        self.custom_emoji_ok = True
        self.media_calls = []
        self.text_calls = []
        self.pinned = []
        self.media_error = media_error

    async def send_media(self, chat_id, kind, media, caption, keyboard=None, silent=False):
        self.media_calls.append((kind, media))
        if self.media_error:
            raise self.media_error
        return {"message_id": 1, kind: {"file_id": "uploaded-id"}}

    async def send_text(self, chat_id, text, keyboard=None, reply_to=None, silent=False):
        self.text_calls.append(text)
        return {"message_id": 2}

    async def pin(self, chat_id, message_id):
        self.pinned.append(message_id)


class FakeChain:
    def __init__(self):
        self.info = PairInfo("0xpair", "0xtoken", "0xweth", True, 18, "NOX", 0)


def make_poster(tmp: Path, tg):
    cfg = Config(bot_token="1:x", chat_id=CHAT, rpc_http="http://node.invalid", rpc_ws="",
                 state_file=tmp / "state.json", media_dir=tmp)
    state = State()
    return Poster(cfg, tg, state, FakeChain()), state


class MediaSelectionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.dir.name)

    def tearDown(self):
        self.dir.cleanup()

    async def test_uploads_local_file_then_reuses_file_id(self):
        (self.tmp / "buy-medium.mp4").write_bytes(b"fake mp4")
        tg = FakeTelegram()
        poster, state = make_poster(self.tmp, tg)
        await poster.post(buy(500), {})
        self.assertEqual(state.media["medium"], {"kind": "animation", "file_id": "uploaded-id"})
        await poster.post(buy(500), {})
        self.assertEqual(tg.media_calls[1][1], "uploaded-id")

    async def test_falls_back_to_text_when_media_is_rejected(self):
        (self.tmp / "buy-medium.mp4").write_bytes(b"fake mp4")
        tg = FakeTelegram(media_error=TelegramError(400, "wrong file identifier"))
        poster, state = make_poster(self.tmp, tg)
        sent = await poster.post(buy(500), {})
        self.assertEqual(sent["message_id"], 2)
        self.assertEqual(len(tg.text_calls), 1)
        self.assertNotIn("medium", state.media)

    async def test_server_error_is_not_retried_as_text(self):
        (self.tmp / "buy-medium.mp4").write_bytes(b"fake mp4")
        tg = FakeTelegram(media_error=TelegramError(403, "bot was kicked"))
        poster, _ = make_poster(self.tmp, tg)
        self.assertIsNone(await poster.post(buy(500), {}))
        self.assertEqual(tg.text_calls, [])

    async def test_text_only_when_no_media_exists(self):
        tg = FakeTelegram()
        poster, _ = make_poster(self.tmp, tg)
        await poster.post(buy(500), {})
        self.assertEqual(tg.media_calls, [])
        self.assertEqual(len(tg.text_calls), 1)

    async def test_whale_pin_is_opt_in(self):
        tg = FakeTelegram()
        poster, state = make_poster(self.tmp, tg)
        await poster.post(buy(50000), {})
        self.assertEqual(tg.pinned, [])
        state.settings.pin_whales = True
        await poster.post(buy(50000), {})
        self.assertEqual(tg.pinned, [2])

    async def test_tier_picks_its_own_media(self):
        for name in ("buy-small.mp4", "buy-whale.mp4"):
            (self.tmp / name).write_bytes(b"fake mp4")
        tg = FakeTelegram()
        poster, _ = make_poster(self.tmp, tg)
        await poster.post(buy(50), {})
        await poster.post(buy(50000), {})
        self.assertEqual(Path(tg.media_calls[0][1]).name, "buy-small.mp4")
        self.assertEqual(Path(tg.media_calls[1][1]).name, "buy-whale.mp4")
