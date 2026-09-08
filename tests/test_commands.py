import tempfile
import unittest
from pathlib import Path

from buybot.commands import Commands
from buybot.state import State

CHAT = -1001234567890
ADMIN = 111
STRANGER = 222


class FakeTelegram:
    def __init__(self, admins=(ADMIN,)):
        self.custom_emoji_ok = True
        self.sent = []
        self.admins = set(admins)

    async def send_text(self, chat_id, text, keyboard=None, reply_to=None, silent=False):
        self.sent.append((chat_id, text))
        return {"message_id": len(self.sent)}

    async def chat_admin_ids(self, chat_id):
        return set(self.admins)

    async def me(self):
        return {"id": 9, "username": "nox_buybot"}


def message(text, user=ADMIN, chat=CHAT, chat_type="supergroup", reply=None, entities=None):
    msg = {"chat": {"id": chat, "type": chat_type}, "from": {"id": user}, "text": text}
    if reply:
        msg["reply_to_message"] = reply
    if entities:
        msg["entities"] = entities
    return msg


class CommandsTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.state = State()
        self.tg = FakeTelegram()
        self.tests_posted = []
        self.cmds = Commands(
            self.tg, self.state, Path(self.dir.name) / "state.json", CHAT, [],
            post_test=self._post_test,
            status_text=self._text("status"),
            stats_text=self._text("stats"),
        )
        self.cmds.bot_username = "nox_buybot"

    def tearDown(self):
        self.dir.cleanup()

    async def _post_test(self, usd):
        self.tests_posted.append(usd)

    def _text(self, value):
        async def inner():
            return value
        return inner

    def last(self):
        return self.tg.sent[-1][1] if self.tg.sent else ""

    async def test_non_admin_is_ignored(self):
        await self.cmds.handle(message("/setmin 999", user=STRANGER))
        self.assertEqual(self.state.settings.min_usd, 25.0)
        self.assertEqual(self.tg.sent, [])

    async def test_other_group_is_ignored(self):
        await self.cmds.handle(message("/setmin 999", chat=-100999))
        self.assertEqual(self.state.settings.min_usd, 25.0)

    async def test_admin_dm_is_accepted(self):
        await self.cmds.handle(message("/setmin 50", chat=ADMIN, chat_type="private"))
        self.assertEqual(self.state.settings.min_usd, 50.0)

    async def test_command_for_another_bot_is_ignored(self):
        await self.cmds.handle(message("/setmin@other_bot 999"))
        self.assertEqual(self.state.settings.min_usd, 25.0)

    async def test_help_is_public(self):
        await self.cmds.handle(message("/help", user=STRANGER))
        self.assertIn("buybot commands", self.last())

    async def test_value_bounds_are_enforced(self):
        for command, field, original in [
            ("/setmin 9999999999", "min_usd", 25.0),
            ("/setstep 0", "emoji_step_usd", 25.0),
            ("/setmax 5000", "emoji_max", 60),
        ]:
            with self.subTest(command=command):
                await self.cmds.handle(message(command))
                self.assertEqual(getattr(self.state.settings, field), original)

    async def test_tier_order_is_enforced(self):
        await self.cmds.handle(message("/settier medium 99999"))
        self.assertEqual(self.state.settings.tier_usd["medium"], 250.0)
        self.assertIn("medium < large < whale", self.last())
        await self.cmds.handle(message("/settier whale 20000"))
        self.assertEqual(self.state.settings.tier_usd["whale"], 20000.0)

    async def test_test_command_is_rate_limited(self):
        await self.cmds.handle(message("/test 100"))
        await self.cmds.handle(message("/test 100"))
        self.assertEqual(self.tests_posted, [100.0])
        self.assertIn("Wait", self.last())

    async def test_links_are_validated_and_capped(self):
        await self.cmds.handle(message("/addlink Trending javascript:alert(1)"))
        self.assertEqual(self.state.settings.links, {})
        await self.cmds.handle(message("/addlink Trending https://t.me/nox"))
        self.assertEqual(self.state.settings.links["Trending"], "https://t.me/nox")
        for i in range(8):
            await self.cmds.handle(message(f"/addlink Link{i} https://example.com/{i}"))
        self.assertLessEqual(len(self.state.settings.links), 6)
        await self.cmds.handle(message("/dellink Trending"))
        self.assertNotIn("Trending", self.state.settings.links)

    async def test_custom_emoji_from_reply(self):
        reply = {"text": "🟢", "entities": [
            {"type": "custom_emoji", "offset": 0, "length": 1, "custom_emoji_id": "5368324170671202286"}]}
        await self.cmds.handle(message("/setemoji", reply=reply))
        self.assertEqual(self.state.settings.custom_emoji_id, "5368324170671202286")

    async def test_bogus_custom_emoji_id_is_refused(self):
        reply = {"text": "x", "entities": [
            {"type": "custom_emoji", "offset": 0, "length": 1, "custom_emoji_id": "<script>"}]}
        await self.cmds.handle(message("/setemoji", reply=reply))
        self.assertEqual(self.state.settings.custom_emoji_id, "")

    async def test_setmedia_requires_a_reply_with_media(self):
        await self.cmds.handle(message("/setmedia whale"))
        self.assertEqual(self.state.media, {})
        reply = {"animation": {"file_id": "CgAC-file"}}
        await self.cmds.handle(message("/setmedia whale", reply=reply))
        self.assertEqual(self.state.media["whale"], {"kind": "animation", "file_id": "CgAC-file"})
        await self.cmds.handle(message("/clearmedia whale"))
        self.assertEqual(self.state.media, {})

    async def test_pause_and_resume(self):
        await self.cmds.handle(message("/pause"))
        self.assertTrue(self.state.settings.paused)
        await self.cmds.handle(message("/resume"))
        self.assertFalse(self.state.settings.paused)

    async def test_unknown_command_is_silent(self):
        await self.cmds.handle(message("/definitelynotacommand"))
        self.assertEqual(self.tg.sent, [])
