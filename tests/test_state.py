import json
import os
import stat
import tempfile
import unittest
from pathlib import Path

from buybot.state import State


class TierTests(unittest.TestCase):
    def test_boundaries(self):
        st = State()
        self.assertEqual(st.tier_for(50), "small")
        self.assertEqual(st.tier_for(250), "medium")
        self.assertEqual(st.tier_for(999), "medium")
        self.assertEqual(st.tier_for(1000), "large")
        self.assertEqual(st.tier_for(5000), "whale")


class RecordTests(unittest.TestCase):
    def test_flags_and_counters(self):
        st = State()
        first = st.record("0x1", "0xa", 100, True, 0.001)
        self.assertFalse(first["ath"])
        self.assertFalse(first["biggest_today"])
        second = st.record("0x2", "0xb", 900, False, 0.002)
        self.assertTrue(second["ath"])
        self.assertTrue(second["biggest_today"])
        self.assertIsNone(st.record("0x2", "0xb", 900, False, 0.002))
        self.assertEqual(st.daily.buys, 2)
        self.assertEqual(st.daily.new_holders, 1)
        self.assertEqual(st.leaderboard()[0], ("0xb", 900.0))
        self.assertEqual(st.streak, 2)

    def test_reorg_forget(self):
        st = State()
        st.record("0xdead", "0xa", 500, True, 0.003)
        st.mark_posted("0xdead", 4242)
        self.assertEqual(st.total_buys, 1)
        self.assertEqual(st.forget("0xdead"), 4242)
        self.assertEqual(st.total_buys, 0)
        self.assertEqual(st.daily.buys, 0)
        self.assertNotIn("0xdead", st.seen_tx)
        self.assertIsNone(st.forget("0xdead"))

    def test_posted_map_is_bounded(self):
        st = State()
        for i in range(260):
            st.mark_posted(f"0x{i:x}", i)
        self.assertEqual(len(st.posted), 200)


class PersistenceTests(unittest.TestCase):
    def test_roundtrip_and_permissions(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "nested" / "state.json"
            st = State()
            st.settings.custom_emoji_id = "5368324170671202286"
            st.media["whale"] = {"kind": "animation", "file_id": "CgAC"}
            st.record("0x9", "0xa", 42, True, 0.01)
            st.mark_posted("0x9", 7)
            st.save(path)

            mode = stat.S_IMODE(os.stat(path).st_mode)
            self.assertEqual(mode, 0o600)

            back = State.load(path)
            self.assertEqual(back.settings.custom_emoji_id, "5368324170671202286")
            self.assertEqual(back.media["whale"]["file_id"], "CgAC")
            self.assertEqual(back.daily.buys, 1)
            self.assertEqual(back.posted["0x9"], 7)

    def test_unknown_keys_are_ignored(self):
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / "state.json"
            path.write_text(json.dumps({"last_block": 12, "settings": {"min_usd": 5.0}, "future": "x"}))
            st = State.load(path)
            self.assertEqual(st.last_block, 12)
            self.assertEqual(st.settings.min_usd, 5.0)
