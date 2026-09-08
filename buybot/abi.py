"""Selectors, decoding and EIP-55 checksums for the Uniswap V2 pool."""
from __future__ import annotations

from .keccak import keccak256

SEL_TOKEN0 = "0x0dfe1681"
SEL_TOKEN1 = "0xd21220a7"
SEL_GET_RESERVES = "0x0902f1ac"
SEL_TOTAL_SUPPLY = "0x18160ddd"
SEL_DECIMALS = "0x313ce567"
SEL_SYMBOL = "0x95d89b41"
SEL_BALANCE_OF = "0x70a08231"
SEL_LATEST_ROUND = "0xfeaf968c"

# Swap(address indexed sender, uint,uint,uint,uint, address indexed to)
TOPIC_SWAP = "0xd78ad95fa46c994b6551d0da85fc275fe613ce37657fb8d5e3d130840159d822"

UINT256_MAX = (1 << 256) - 1


def pad_address(addr: str) -> str:
    return addr.lower().replace("0x", "").rjust(64, "0")


def encode_call(selector: str, *addresses: str) -> str:
    return selector + "".join(pad_address(a) for a in addresses)


def words(data: str) -> list[int]:
    hexstr = data[2:] if data.startswith("0x") else data
    return [int(hexstr[i : i + 64], 16) for i in range(0, len(hexstr) - len(hexstr) % 64, 64)]


def decode_uint(data: str) -> int:
    ws = words(data)
    return ws[0] if ws else 0


def decode_address(data: str) -> str:
    return "0x" + data[-40:].lower()


def topic_to_address(topic: str) -> str:
    return "0x" + topic[-40:].lower()


def decode_string(data: str) -> str:
    """Dynamic string, falling back to the bytes32 symbols some tokens return."""
    hexstr = data[2:] if data.startswith("0x") else data
    if not hexstr:
        return ""
    ws = words(hexstr)
    if len(ws) >= 3 and ws[0] == 32:
        length = ws[1]
        raw = bytes.fromhex(hexstr[128 : 128 + length * 2])
        return raw.decode("utf-8", "replace")
    return bytes.fromhex(hexstr[:64]).rstrip(b"\x00").decode("utf-8", "replace")


def to_checksum(addr: str) -> str:

    body = addr.lower().replace("0x", "")
    h = keccak256(body.encode()).hex()
    out = [c.upper() if c in "abcdef" and int(hc, 16) >= 8 else c for c, hc in zip(body, h)]
    return "0x" + "".join(out)
