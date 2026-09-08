import os
import unittest
from contextlib import contextmanager

from buybot.config import NOX_TOKEN, Config, ConfigError

VALID = {
    "BOT_TOKEN": "123456789:AAHdqTcvCH1vGWJxfSeofSAs0K5PALDsaw",
    "CHAT_ID": "-1001234567890",
    "RPC_HTTP": "https://eth-mainnet.example/v2/key",
}
MANAGED = ("BOT_TOKEN", "CHAT_ID", "RPC_HTTP", "RPC_WS", "TOKEN_ADDRESS", "PAIR_ADDRESS",
           "ADMIN_IDS", "CONFIRMATIONS", "POLL_SECONDS", "LOG_LEVEL", "WEBSITE",
           "STATE_FILE", "MEDIA_DIR")


@contextmanager
def env(**overrides):
    saved = {k: os.environ.get(k) for k in MANAGED}
    for k in MANAGED:
        os.environ.pop(k, None)
    os.environ.update({**VALID, **{k: v for k, v in overrides.items() if v is not None}})
    try:
        yield
    finally:
        for k, v in saved.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v


class ConfigTests(unittest.TestCase):
    def test_defaults(self):
        with env():
            cfg = Config.from_env()
        self.assertEqual(cfg.chat_id, -1001234567890)
        self.assertEqual(cfg.token, NOX_TOKEN)
        self.assertEqual(cfg.confirmations, 0)
        self.assertEqual(cfg.rpc_ws, "")

    def test_admin_ids_and_websocket(self):
        with env(ADMIN_IDS="111, 222;333", RPC_WS="wss://node.example"):
            cfg = Config.from_env()
        self.assertEqual(cfg.admin_ids, [111, 222, 333])
        self.assertEqual(cfg.rpc_ws, "wss://node.example")

    def test_rejects_bad_values(self):
        cases = [
            {"BOT_TOKEN": "not-a-token"},
            {"CHAT_ID": "my-group"},
            {"RPC_HTTP": "ftp://node.example"},
            {"RPC_WS": "https://node.example"},
            {"TOKEN_ADDRESS": "0x1234"},
            {"PAIR_ADDRESS": "nope"},
            {"ADMIN_IDS": "alice"},
            {"CONFIRMATIONS": "-1"},
            {"CONFIRMATIONS": "999"},
            {"POLL_SECONDS": "0.1"},
            {"LOG_LEVEL": "LOUD"},
            {"WEBSITE": "javascript:alert(1)"},
        ]
        for overrides in cases:
            with self.subTest(**overrides), env(**overrides), self.assertRaises(ConfigError):
                Config.from_env()

    def test_missing_required(self):
        with env():
            os.environ.pop("RPC_HTTP")
            with self.assertRaises(ConfigError):
                Config.from_env()
