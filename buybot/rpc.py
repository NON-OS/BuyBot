"""JSON-RPC over HTTP with WebSocket subscriptions.

Providers disagree on batch size and eth_getLogs range; both limits are
discovered at runtime and the client degrades instead of failing."""
from __future__ import annotations

import asyncio
import itertools
import json
import logging
from collections.abc import AsyncIterator
from typing import Any

import aiohttp

log = logging.getLogger("buybot.rpc")


class RpcError(RuntimeError):
    pass


def _is_range_limit(err: Any) -> bool:
    text = str(err).lower()
    return any(k in text for k in ("range", "limit", "block", "archive", "exceed", "too many", "too large"))


def _is_batch_limit(err: Any) -> bool:
    text = str(err).lower()
    return "batch" in text or "too many" in text


class Rpc:
    def __init__(self, http_url: str, ws_url: str = "", timeout: float = 20.0):
        self.http_url = http_url
        self.ws_url = ws_url
        self._secrets = [u for u in (http_url, ws_url) if u]
        self._ids = itertools.count(1)
        self._timeout = aiohttp.ClientTimeout(total=timeout)
        self._session: aiohttp.ClientSession | None = None
        self.batch_size = 20
        self.max_log_span = 2000

    async def __aenter__(self) -> Rpc:
        self._session = aiohttp.ClientSession(timeout=self._timeout)
        return self

    async def __aexit__(self, *exc: Any) -> None:
        if self._session:
            await self._session.close()

    def _redact(self, text: str) -> str:
        for url in self._secrets:
            text = text.replace(url, "<rpc>")
        return text

    def host(self) -> str:
        return (self.ws_url or self.http_url).split("/")[2].split("@")[-1]

    async def call(self, method: str, params: list[Any]) -> Any:
        assert self._session, "use `async with Rpc(...)`"
        payload = {"jsonrpc": "2.0", "id": next(self._ids), "method": method, "params": params}
        delay = 1.0
        for attempt in range(6):
            try:
                async with self._session.post(self.http_url, json=payload) as resp:
                    if resp.status == 429 or resp.status >= 500:
                        raise RpcError(f"http {resp.status}")
                    body = await resp.json(content_type=None)
            except (aiohttp.ClientError, asyncio.TimeoutError, RpcError) as exc:
                if attempt == 5:
                    raise RpcError(f"{method} failed: {exc}") from exc
                log.warning("rpc %s retry %d: %s", method, attempt + 1, self._redact(str(exc)))
                await asyncio.sleep(delay)
                delay = min(delay * 2, 20)
                continue
            if "error" in body:
                raise RpcError(f"{method}: {body['error']}")
            return body.get("result")
        raise RpcError(method)

    async def batch(self, calls: list[tuple[str, list[Any]]]) -> list[Any]:

        if not calls:
            return []
        out: list[Any] = []
        for i in range(0, len(calls), self.batch_size):
            out.extend(await self._batch_chunk(calls[i : i + self.batch_size]))
        return out

    async def _batch_chunk(self, calls: list[tuple[str, list[Any]]]) -> list[Any]:
        assert self._session
        if self.batch_size > 1:
            payload = [
                {"jsonrpc": "2.0", "id": i, "method": m, "params": p} for i, (m, p) in enumerate(calls)
            ]
            try:
                async with self._session.post(self.http_url, json=payload) as resp:
                    body = await resp.json(content_type=None)
                if isinstance(body, list) and len(body) == len(calls):
                    ordered = sorted(body, key=lambda x: x.get("id", 0))
                    if not any("error" in item for item in ordered):
                        return [item.get("result") for item in ordered]
                    errs = [item["error"] for item in ordered if "error" in item]
                    if not _is_batch_limit(errs[0]):
                        raise RpcError(str(errs[0]))
                elif isinstance(body, dict) and "error" in body and not _is_batch_limit(body["error"]):
                    raise RpcError(str(body["error"]))
                log.warning("provider rejected batch of %d; switching to sequential calls", len(calls))
                self.batch_size = 1
            except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as exc:
                log.debug("batch transport error (%s); sequential fallback", exc)
        return [await self.call(m, p) for m, p in calls]

    async def block_number(self) -> int:
        return int(await self.call("eth_blockNumber", []), 16)

    async def eth_call(self, to: str, data: str, block: str | int = "latest") -> str:
        tag = block if isinstance(block, str) else hex(block)
        return await self.call("eth_call", [{"to": to, "data": data}, tag])

    async def get_logs(self, address: str, topics: list[Any], from_block: int, to_block: int) -> list[dict]:

        out: list[dict] = []
        start = from_block
        while start <= to_block:
            end = min(to_block, start + self.max_log_span - 1)
            try:
                out.extend(await self.call(
                    "eth_getLogs",
                    [{"address": address, "topics": topics, "fromBlock": hex(start), "toBlock": hex(end)}],
                ))
                start = end + 1
            except RpcError as exc:
                if self.max_log_span <= 10 or not _is_range_limit(exc):
                    raise
                self.max_log_span = max(10, self.max_log_span // 4)
                log.warning("eth_getLogs range rejected (%s); span now %d blocks", str(exc)[:80], self.max_log_span)
        return out

    async def get_transaction(self, tx_hash: str) -> dict:
        return await self.call("eth_getTransactionByHash", [tx_hash])

    async def get_block(self, number: int) -> dict:
        return await self.call("eth_getBlockByNumber", [hex(number), False])

    async def new_heads(self) -> AsyncIterator[int]:

        async for result in self.subscribe(["newHeads"]):
            yield int(result["number"], 16)

    async def subscribe_logs(self, address: str, topics: list[Any]) -> AsyncIterator[dict]:

        async for result in self.subscribe(["logs", {"address": address, "topics": topics}]):
            yield result

    async def subscribe(self, params: list[Any]) -> AsyncIterator[Any]:
        import websockets

        while True:
            try:
                async with websockets.connect(self.ws_url, ping_interval=15, ping_timeout=20, max_size=16_000_000) as ws:
                    await ws.send(json.dumps({"jsonrpc": "2.0", "id": 1, "method": "eth_subscribe", "params": params}))
                    log.info("subscribed %s", params[0])
                    async for raw in ws:
                        msg = json.loads(raw)
                        p = msg.get("params")
                        if p and "result" in p:
                            yield p["result"]
            except asyncio.CancelledError:
                raise
            except Exception as exc:  # any failure: reconnect
                log.warning("ws %s dropped: %s; reconnecting in 3s", params[0], self._redact(str(exc)))
                await asyncio.sleep(3)
