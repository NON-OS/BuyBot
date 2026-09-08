import unittest

from buybot.telegram import Telegram, TelegramError, strip_html


class SendingTelegram(Telegram):
    """Records calls and fails the first attempt with a scripted error."""

    def __init__(self, first_error=None):
        super().__init__("123456:secret-token-value")
        self.calls = []
        self.first_error = first_error

    async def api(self, method, files=None, **params):
        self.calls.append(params)
        if self.first_error and len(self.calls) == 1:
            raise self.first_error
        return {"message_id": len(self.calls)}


class ParseFallbackTests(unittest.IsolatedAsyncioTestCase):
    async def test_unparsable_html_is_sent_as_plain_text(self):
        tg = SendingTelegram(TelegramError(400, 'Bad Request: can\'t parse entities: Unsupported start tag "tier|all"'))
        await tg.send_text(-100, "Use /setmedia <tier|all> please")
        self.assertEqual(len(tg.calls), 2)
        self.assertNotIn("parse_mode", tg.calls[1])
        self.assertIn("<tier|all>", tg.calls[1]["text"])

    async def test_custom_emoji_rejection_falls_back_once(self):
        tg = SendingTelegram(TelegramError(400, "Bad Request: unsupported custom emoji"))
        text = '<b>BUY</b>\n<tg-emoji emoji-id="123">🟢</tg-emoji>'
        await tg.send_text(-100, text)
        self.assertEqual(len(tg.calls), 2)
        self.assertNotIn("tg-emoji", tg.calls[1]["text"])
        self.assertIn("🟢", tg.calls[1]["text"])
        self.assertFalse(tg.custom_emoji_ok)

        tg.first_error = None
        await tg.send_text(-100, text)
        self.assertNotIn("tg-emoji", tg.calls[2]["text"])

    async def test_other_errors_are_raised(self):
        tg = SendingTelegram(TelegramError(403, "bot was blocked by the user"))
        with self.assertRaises(TelegramError):
            await tg.send_text(-100, "hello")

    async def test_unsupported_media_kind(self):
        with self.assertRaises(TelegramError):
            await SendingTelegram().send_media(-100, "hologram", "file-id", "caption")


class StripHtmlTests(unittest.TestCase):
    def test_tags_removed_and_entities_restored(self):
        out = strip_html('<b>NOX BUY!</b> <a href="https://x">Txn</a> a &lt; b &amp; c')
        self.assertEqual(out, "NOX BUY! Txn a < b & c")

    def test_custom_emoji_becomes_its_glyph(self):
        self.assertEqual(strip_html('<tg-emoji emoji-id="1">🟢</tg-emoji>x'), "🟢x")


class RedactionTests(unittest.TestCase):
    def test_token_never_appears(self):
        tg = SendingTelegram()
        message = tg._redact("failed to POST https://api.telegram.org/bot123456:secret-token-value/sendMessage")
        self.assertNotIn("secret-token-value", message)
        self.assertIn("<token>", message)
