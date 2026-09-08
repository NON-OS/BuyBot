import unittest
from decimal import Decimal

from buybot import abi
from buybot.format import fmt_amount, fmt_price, fmt_usd, short_addr


class ChecksumTests(unittest.TestCase):
    def test_known_addresses(self):
        cases = {
            "0x0a26c80be4e060e688d7c23addb92cbb5d2c9eca": "0x0a26c80Be4E060e688d7C23aDdB92cBb5D2C9eCA",
            "0xfb6916095ca1df60bb79ce92ce3ea74c37c5d359": "0xfB6916095ca1df60bB79Ce92cE3Ea74c37c5d359",
            "0x5aaeb6053f3e94c9b9a09f33669435e7ef1beaed": "0x5aAeb6053F3E94C9b9A09f33669435E7Ef1BeAed",
            "0xde709f2102306220921060314715629080e2fb77": "0xde709f2102306220921060314715629080e2fb77",
        }
        for lower, checksummed in cases.items():
            self.assertEqual(abi.to_checksum(lower), checksummed)

    def test_short_addr(self):
        self.assertEqual(short_addr("0x5aaeb6053f3e94c9b9a09f33669435e7ef1beaed"), "0x5aAe…eAed")


class DecodeTests(unittest.TestCase):
    def test_words(self):
        data = "0x" + "".join(hex(v)[2:].rjust(64, "0") for v in (0, 10**18, 5 * 10**21, 0))
        self.assertEqual(abi.words(data), [0, 10**18, 5 * 10**21, 0])

    def test_string_dynamic_and_bytes32(self):
        dyn = "0x" + hex(32)[2:].rjust(64, "0") + hex(3)[2:].rjust(64, "0") + b"NOX".hex().ljust(64, "0")
        self.assertEqual(abi.decode_string(dyn), "NOX")
        self.assertEqual(abi.decode_string("0x" + b"MKR".hex().ljust(64, "0")), "MKR")

    def test_empty_returndata(self):
        self.assertEqual(abi.decode_uint("0x"), 0)
        self.assertEqual(abi.decode_string("0x"), "")

    def test_encode_call(self):
        call = abi.encode_call(abi.SEL_BALANCE_OF, "0x000000000000000000000000000000000000dEaD")
        self.assertEqual(len(call), 10 + 64)
        self.assertTrue(call.endswith("dead"))


class NumberTests(unittest.TestCase):
    def test_price(self):
        self.assertEqual(fmt_price(Decimal("0.002734")), "$0.002734")
        self.assertEqual(fmt_price(Decimal("0.000000123456")), "$0.0₆1234")
        self.assertEqual(fmt_price(Decimal("12.5")), "$12.5")
        self.assertEqual(fmt_price(Decimal(0)), "$0")

    def test_usd_and_amounts(self):
        self.assertEqual(fmt_usd(Decimal("2169410"), 0), "$2.17M")
        self.assertEqual(fmt_usd(Decimal("1234.5")), "$1,234.50")
        self.assertEqual(fmt_usd(Decimal("4200000000"), 0), "$4.20B")
        self.assertEqual(fmt_amount(Decimal("451234.12")), "451,234")
        self.assertEqual(fmt_amount(Decimal("0.5123"), 4), "0.5123")
