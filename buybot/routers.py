ROUTERS = {
    "0x7a250d5630b4cf539739df2c5dacb4c659f2488d": "Uniswap V2",
    "0x3fc91a3afd70395cd496c647d5a6cc9d4b2b7fad": "Uniswap",
    "0xef1c6e67703c7bd7107eed8303fbe6ec2554bf6b": "Uniswap",
    "0x66a9893cc07d91d95644aedd05d03f95e1dba8af": "Uniswap",
    "0xe592427a0aece92de3edee1f18e0157c05861564": "Uniswap V3",
    "0x68b3465833fb72a70ecdf485e0e4c7bd8665fc45": "Uniswap V3",
    "0x1111111254eeb25477b68fb85ed929f73a960582": "1inch",
    "0x111111125421ca6dc452d289314280a0f8842a65": "1inch",
    "0xdef1c0ded9bec7f1a1670819833240f027b25eff": "0x / Matcha",
    "0x6a000f20005980200259b80c5102003040001068": "ParaSwap",
    "0x6131b5fae19ea4f9d964eac0408e4408b66337b5": "KyberSwap",
    "0x9008d19f58aabd9ed0d60971565aa8510560ab41": "CoW Swap",
    "0x881d40237659c251811cec9c364ef91dc08d300c": "MetaMask Swap",
    "0x7d0ccaa3fac1e5a943c5168b6ced828691b46b36": "OKX DEX",
    "0x80a64c6d7f12c47b7c66c5b4e20e72bc1fcd5d9e": "Maestro",
    "0x3328f7f4a1d1c57c35df56bbf0c9dcafca309c49": "Banana Gun",
}


def router_name(address: str) -> str:
    return ROUTERS.get(address.lower(), "")
