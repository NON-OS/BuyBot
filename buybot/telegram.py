"""Telegram Bot API client.

Custom emoji only render for bots that own a Fragment username; when Telegram
rejects them the client remembers and sends the plain emoji instead."""
from __future__ import annotations

import asyncio
import json
import logging
import re
from pathlib import Path
from typing import Any

import aiohttp

from .media import FIELD, MAX_UPLOAD_BYTES, METHOD

log = logging.getLogger("buybot.tg")

TG_EMOJI_RE = re.compile(r'<tg-emoji emoji-id="[^"]*">(.*?)</tg-emoji>', re.S)
# Only the tags Telegram itself understands, so text like "<tier|all>" survives.
TAG_RE = re.compile(r"</?(?:b|strong|i|em|u|ins|s|strike|del|a|code|pre|span|blockquote|tg-emoji)\b[^>]*>", re.I)


def strip_html(text: str) -> str:
    plain = TAG_RE.sub("", TG_EMOJI_RE.sub(r"\1", text))
    return plain.replace("&lt;", "<").replace("&gt;", ">").replace("&amp;", "&")

class TelegramError(RuntimeError):
    def __init__(self, code: int, description: str):
        super().__init__(f"{code}: {description}")
        self.code = code
        self.description = description


class Telegram:
    def __init__(self, token: str):
        self._token = token
        self.base = f"https://api.telegram.org/bot{token}/"
        self._session: aiohttp.ClientSession | None = None
        self.custom_emoji_ok = True

    async def __aenter__(self) -> Telegram:
        self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60))
        return self

    async def __aexit__(self, *exc: Any) -> None:
        if self._session:
            await self._session.close()

    def _redact(self, text: str) -> str:
        return text.replace(self._token, "<token>")

    async def api(self, method: str, files: dict[str, Path] | None = None, **params: Any) -> Any:
        assert self._session, "use `async with Telegram(...)`"
        payloads: dict[str, tuple[bytes, str]] = {}
        for name, path in (files or {}).items():
            if path.stat().st_size > MAX_UPLOAD_BYTES:
                raise TelegramError(0, f"{path.name} exceeds the 50 MB upload limit")
            payloads[name] = (path.read_bytes(), path.name)
        for attempt in range(5):
            form = aiohttp.FormData()
            for key, value in params.items():
                if value is None:
                    continue
                form.add_field(key, json.dumps(value) if isinstance(value, (dict, list)) else str(value))
            for name, (blob, filename) in payloads.items():
                form.add_field(name, blob, filename=filename)
            try:
                async with self._session.post(self.base + method, data=form) as resp:
                    body = await resp.json(content_type=None)
            except (aiohttp.ClientError, asyncio.TimeoutError, ValueError) as exc:
                log.warning("telegram %s transport error: %s", method, self._redact(str(exc)))
                await asyncio.sleep(2 * (attempt + 1))
                continue
            if body.get("ok"):
                return body["result"]
            code = int(body.get("error_code", 0))
            desc = self._redact(str(body.get("description", "")))
            if code == 429:
                wait = int(body.get("parameters", {}).get("retry_after", 5))
                log.warning("flood wait %ss on %s", wait, method)
                await asyncio.sleep(min(wait, 120) + 1)
                continue
            raise TelegramError(code, desc)
        raise TelegramError(0, f"{method}: gave up after retries")

    async def send_text(self, chat_id: int, text: str, keyboard: list | None = None,
                        reply_to: int | None = None, silent: bool = False) -> dict:
        return await self._send_with_fallback(
            "sendMessage", "text", keyboard=keyboard, chat_id=chat_id, text=text,
            reply_to_message_id=reply_to, disable_notification=silent, disable_web_page_preview=True,
        )

    async def send_media(self, chat_id: int, kind: str, media: str | Path, caption: str,
                         keyboard: list | None = None, silent: bool = False) -> dict:
        """Accepts a file_id or a local path."""
        if kind not in METHOD:
            raise TelegramError(0, f"unsupported media kind {kind!r}")
        files = {FIELD[kind]: media} if isinstance(media, Path) else None
        ref = {} if files else {FIELD[kind]: media}
        if kind == "sticker":
            # stickers carry no caption, so the text follows as its own message
            await self.api(METHOD[kind], files=files, chat_id=chat_id, disable_notification=silent, **ref)
            return await self.send_text(chat_id, caption, keyboard, silent=silent)
        return await self._send_with_fallback(
            METHOD[kind], "caption", keyboard=keyboard, files=files, chat_id=chat_id, caption=caption,
            disable_notification=silent, **ref,
        )

    async def _send_with_fallback(self, method: str, text_field: str, keyboard: list | None = None,
                                  files: dict | None = None, **params: Any) -> dict:
        text = params[text_field]
        if not self.custom_emoji_ok:
            params[text_field] = TG_EMOJI_RE.sub(r"\1", text)
        markup = {"inline_keyboard": keyboard} if keyboard else None
        try:
            return await self.api(method, files=files, parse_mode="HTML", reply_markup=markup, **params)
        except TelegramError as exc:
            if exc.code == 400 and "<tg-emoji" in params[text_field]:
                log.warning("custom emoji rejected (%s); using standard emoji from now on", exc.description)
                self.custom_emoji_ok = False
                params[text_field] = TG_EMOJI_RE.sub(r"\1", text)
                return await self.api(method, files=files, parse_mode="HTML", reply_markup=markup, **params)
            if exc.code == 400 and "parse entities" in exc.description:
                # An unescaped angle bracket somewhere in the text. Send it as
                # plain text rather than dropping the message.
                log.warning("HTML rejected (%s); sending as plain text", exc.description)
                params[text_field] = strip_html(text)
                return await self.api(method, files=files, reply_markup=markup, **params)
            raise

    async def pin(self, chat_id: int, message_id: int) -> None:
        try:
            await self.api("pinChatMessage", chat_id=chat_id, message_id=message_id, disable_notification=True)
        except TelegramError as exc:
            log.warning("pin failed: %s", exc)

    async def delete(self, chat_id: int, message_id: int) -> bool:
        try:
            await self.api("deleteMessage", chat_id=chat_id, message_id=message_id)
            return True
        except TelegramError as exc:
            log.warning("delete failed: %s", exc)
            return False

    async def get_updates(self, offset: int, timeout: int = 30) -> list[dict]:
        try:
            return await self.api("getUpdates", offset=offset, timeout=timeout, allowed_updates=["message"])
        except TelegramError as exc:
            log.warning("getUpdates: %s", exc)
            await asyncio.sleep(3)
            return []

    async def chat_admin_ids(self, chat_id: int) -> set[int]:
        try:
            admins = await self.api("getChatAdministrators", chat_id=chat_id)
            return {int(a["user"]["id"]) for a in admins}
        except TelegramError as exc:
            log.warning("getChatAdministrators: %s", exc)
            return set()

    async def me(self) -> dict:
        return await self.api("getMe")

    async def chat(self, chat_id: int) -> dict:
        return await self.api("getChat", chat_id=chat_id)

    async def delete_webhook(self) -> None:
        try:
            await self.api("deleteWebhook", drop_pending_updates=False)
        except TelegramError as exc:
            log.debug("deleteWebhook: %s", exc)
