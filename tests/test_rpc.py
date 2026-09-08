import unittest

from buybot.rpc import Rpc, RpcError

BATCH_LIMIT = {"code": 31, "message": "Batch of more than 3 requests are not allowed on free plan"}
RANGE_LIMIT = {"code": -32602, "message": "eth_getLogs is limited to 0 - 50 blocks range"}
REAL_ERROR = {"code": -32000, "message": "execution reverted"}


class ScriptedRpc(Rpc):
    """Answers eth_call/eth_getLogs from a script instead of a node."""

    def __init__(self, log_span_limit=None, batch_errors=0):
        super().__init__("http://node.invalid")
        self.log_span_limit = log_span_limit
        self.batch_errors = batch_errors
        self.log_calls = []
        self.served = []
        self.single_calls = 0

    async def call(self, method, params):
        if method == "eth_getLogs":
            frm = int(params[0]["fromBlock"], 16)
            to = int(params[0]["toBlock"], 16)
            self.log_calls.append((frm, to))
            if self.log_span_limit is not None and to - frm + 1 > self.log_span_limit:
                raise RpcError(f"eth_getLogs: {RANGE_LIMIT}")
            self.served.append((frm, to))
            return [{"blockNumber": hex(frm)}]
        self.single_calls += 1
        return "0x" + "0" * 64

    async def _batch_chunk(self, calls):
        if self.batch_errors > 0:
            self.batch_errors -= 1
            self.batch_size = 1
            return [await self.call(m, p) for m, p in calls]
        return await super()._batch_chunk(calls)


class LogRangeTests(unittest.IsolatedAsyncioTestCase):
    async def test_range_cap_shrinks_span_and_covers_everything(self):
        rpc = ScriptedRpc(log_span_limit=50)
        out = await rpc.get_logs("0xpair", ["0xtopic"], 1000, 1199)
        self.assertLessEqual(rpc.max_log_span, 50)
        self.assertEqual(rpc.served[0][0], 1000)
        self.assertEqual(rpc.served[-1][1], 1199)
        for (_, prev_to), (next_from, _) in zip(rpc.served, rpc.served[1:]):
            self.assertEqual(next_from, prev_to + 1)
        self.assertEqual(len(out), len(rpc.served))

    async def test_unrelated_error_is_not_treated_as_a_range_cap(self):
        class Reverting(ScriptedRpc):
            async def call(self, method, params):
                raise RpcError(f"eth_getLogs: {REAL_ERROR}")

        rpc = Reverting()
        with self.assertRaises(RpcError):
            await rpc.get_logs("0xpair", ["0xtopic"], 1, 10)
        self.assertEqual(rpc.max_log_span, 2000)

    async def test_single_window_needs_one_request(self):
        rpc = ScriptedRpc()
        await rpc.get_logs("0xpair", ["0xtopic"], 1, 100)
        self.assertEqual(len(rpc.log_calls), 1)


class BatchTests(unittest.IsolatedAsyncioTestCase):
    async def test_falls_back_to_sequential_calls(self):
        rpc = ScriptedRpc(batch_errors=1)
        calls = [("eth_call", [{"to": "0x1", "data": "0x2"}, "latest"]) for _ in range(6)]
        out = await rpc.batch(calls)
        self.assertEqual(len(out), 6)
        self.assertEqual(rpc.batch_size, 1)
        self.assertEqual(rpc.single_calls, 6)

    async def test_empty_batch(self):
        self.assertEqual(await ScriptedRpc().batch([]), [])


class RedactionTests(unittest.TestCase):
    def test_urls_are_stripped_from_messages(self):
        rpc = Rpc("https://eth.example/v2/SECRETKEY", "wss://eth.example/v2/SECRETKEY")
        message = rpc._redact("failed to reach https://eth.example/v2/SECRETKEY now")
        self.assertNotIn("SECRETKEY", message)
        self.assertIn("<rpc>", message)

    def test_host_prefers_websocket(self):
        self.assertEqual(Rpc("https://a.example/k", "wss://b.example/k").host(), "b.example")
        self.assertEqual(Rpc("https://a.example/k").host(), "a.example")

    def test_host_drops_basic_auth(self):
        self.assertEqual(Rpc("https://user:pass@a.example/k").host(), "a.example")
