import unittest
from decimal import Decimal

from buybot import abi
from buybot.chain import Chain
from buybot.models import PairInfo
from buybot.rpc import Rpc
from buybot.swaps import Swaps
from tests.helpers import word

TOKEN = "0x0a26c80Be4E060e688d7C23aDdB92cBb5D2C9eCA"
PAIR = "0x07CE5889D2EB681Af3bD61db24Ab2602c502Bd1B"
WETH = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
FEED = "0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419"
BUYER = "0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAed"
UNISWAP_V2 = "0x7a250d5630B4cF539739dF2C5dAcb4c659F2488D"


class FakeRpc(Rpc):
    def __init__(self, holder_balance=0):
        super().__init__("http://node.invalid")
        self.methods = []
        self.holder_balance = holder_balance

    async def batch(self, calls):
        self.methods.extend(m for m, _ in calls)
        out = []
        for method, params in calls:
            if method == "eth_getTransactionByHash":
                out.append({"from": BUYER, "to": UNISWAP_V2})
            elif method == "eth_getBlockByNumber":
                out.append({"timestamp": hex(1_700_000_000)})
            else:
                data = params[0]["data"]
                block = params[1]
                if data == abi.SEL_GET_RESERVES:
                    out.append("0x" + word(31_000_000 * 10**18) + word(20 * 10**18) + word(0))
                elif data == abi.SEL_LATEST_ROUND:
                    out.append("0x" + word(1) + word(2500 * 10**8) + word(0) + word(0) + word(1))
                elif data == abi.SEL_TOTAL_SUPPLY:
                    out.append("0x" + word(800_000_000 * 10**18))
                elif data.startswith(abi.SEL_BALANCE_OF) and BUYER[2:].lower() in data:
                    prior = block == hex(99)
                    held = self.holder_balance
                    out.append("0x" + word(held if prior else held + 100_000 * 10**18))
                else:
                    out.append("0x" + word(0))
        return out


def swap_log(tx, block, eth_in=0, tok_out=0, tok_in=0, eth_out=0):
    topics = [abi.TOPIC_SWAP, "0x" + word(0), "0x" + "0" * 24 + BUYER[2:].lower()]
    return {
        "transactionHash": tx,
        "blockNumber": hex(block),
        "topics": topics,
        "data": "0x" + word(tok_in) + word(eth_in) + word(tok_out) + word(eth_out),
    }


def make_swaps(holder_balance=0):
    rpc = FakeRpc(holder_balance)
    chain = Chain(rpc, TOKEN, PAIR, WETH, FEED, "NOX")
    chain.info = PairInfo(chain.pair, chain.token, chain.weth, True, 18, "NOX", 800_000_000 * 10**18)
    return rpc, Swaps(chain)


class DecodeTests(unittest.IsolatedAsyncioTestCase):
    async def test_split_fills_become_one_buy(self):
        rpc, swaps = make_swaps()
        logs = [
            swap_log("0xaa", 100, eth_in=10**17, tok_out=50_000 * 10**18),
            swap_log("0xaa", 100, eth_in=10**17, tok_out=50_000 * 10**18),
            swap_log("0xbb", 100, tok_in=10_000 * 10**18, eth_out=10**16),
        ]
        buys = await swaps.from_logs(logs)
        self.assertEqual(len(buys), 1)
        b = buys[0]
        self.assertEqual(b.swaps, 2)
        self.assertEqual(b.eth_in, Decimal("0.2"))
        self.assertEqual(b.tokens_out, Decimal(100_000))
        self.assertEqual(b.usd, Decimal(500))
        self.assertTrue(b.is_new_holder)
        self.assertEqual(b.router, UNISWAP_V2.lower())
        self.assertEqual(b.timestamp, 1_700_000_000)
        self.assertNotIn("eth_getLogs", rpc.methods)
        self.assertEqual(rpc.methods.count("eth_getTransactionByHash"), 1)

    async def test_sells_are_counted_not_posted(self):
        _, swaps = make_swaps()
        logs = [
            swap_log("0xbb", 100, tok_in=10_000 * 10**18, eth_out=10**16),
            swap_log("0xcc", 100, tok_in=20_000 * 10**18, eth_out=2 * 10**16),
        ]
        self.assertEqual(swaps.count_sells(logs), 2)
        self.assertEqual(await swaps.from_logs(logs), [])

    async def test_removed_and_malformed_logs_are_skipped(self):
        _, swaps = make_swaps()
        removed = swap_log("0xaa", 100, eth_in=10**17, tok_out=10**18)
        removed["removed"] = True
        short = {"transactionHash": "0xdd", "blockNumber": hex(100),
                 "topics": [abi.TOPIC_SWAP], "data": "0x" + word(1)}
        self.assertEqual(await swaps.from_logs([removed, short]), [])
        self.assertEqual(swaps.count_sells([removed, short]), 0)

    async def test_existing_holder_position(self):
        _, swaps = make_swaps(holder_balance=100_000 * 10**18)
        logs = [swap_log("0xaa", 100, eth_in=10**17, tok_out=100_000 * 10**18)]
        buy = (await swaps.from_logs(logs))[0]
        self.assertFalse(buy.is_new_holder)
        self.assertEqual(buy.balance_before, Decimal(100_000))
        self.assertEqual(buy.position_pct, Decimal(100))


class TokenOrderTests(unittest.IsolatedAsyncioTestCase):
    async def test_token1_pair_reads_the_other_side(self):
        rpc = FakeRpc()
        chain = Chain(rpc, TOKEN, PAIR, WETH, FEED, "NOX")
        chain.info = PairInfo(chain.pair, chain.token, chain.weth, False, 18, "NOX", 0)
        swaps = Swaps(chain)
        log = {
            "transactionHash": "0xaa",
            "blockNumber": hex(100),
            "topics": [abi.TOPIC_SWAP, "0x" + word(0), "0x" + "0" * 24 + BUYER[2:].lower()],
            "data": "0x" + word(10**17) + word(0) + word(0) + word(100_000 * 10**18),
        }
        buys = await swaps.from_logs([log])
        self.assertEqual(len(buys), 1)
        self.assertEqual(buys[0].eth_in, Decimal("0.1"))
