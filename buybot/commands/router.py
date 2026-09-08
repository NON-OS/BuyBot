"""Update loop, authorisation and dispatch for the admin commands.

Commands are accepted only in the configured chat or in private, and only
from that chat's administrators plus ADMIN_IDS.
"""
from __future__ import annotations

import logging
import time
from collections.abc import Awaitable
from pathlib import Path
from typing import Callable

from ..state import State
from ..telegram import Telegram, TelegramError
from .appearance import AppearanceCommands
from .control import ControlCommands
from .help import HELP
from .limits import ADMIN_CACHE_SECONDS

log = logging.getLogger("buybot.cmd")


class Commands(ControlCommands, AppearanceCommands):
    def __init__(self, tg: Telegram, state: State, state_path: Path, chat_id: int, admin_ids: list[int],
                 post_test: Callable[[float], Awaitable[None]], status_text: Callable[[], Awaitable[str]],
                 stats_text: Callable[[], Awaitable[str]]):
        self.tg = tg
        self.st = state
        self.path = state_path
        self.chat_id = chat_id
        self.static_admins = set(admin_ids)
        self.post_test = post_test
        self.status_text = status_text
        self.stats_text = stats_text
        self.bot_username = ""
        self._admins: set[int] = set()
        self._admins_at = 0.0
        self._last_test = 0.0

    async def run(self) -> None:
        me = await self.tg.me()
        self.bot_username = me.get("username", "")
        await self.tg.delete_webhook()
        offset = 0
        while True:
            for update in await self.tg.get_updates(offset):
                offset = update["update_id"] + 1
                msg = update.get("message")
                if not msg:
                    continue
                try:
                    await self.handle(msg)
                except TelegramError as exc:
                    log.warning("command failed: %s", exc)
                except (ValueError, IndexError, KeyError) as exc:
                    log.info("bad command input: %s", exc)
                    await self.tg.send_text(msg["chat"]["id"], "Bad value. Send /help for usage.")

    async def is_admin(self, user_id: int) -> bool:
        if user_id in self.static_admins:
            return True
        if time.time() - self._admins_at > ADMIN_CACHE_SECONDS:
            self._admins = await self.tg.chat_admin_ids(self.chat_id)
            self._admins_at = time.time()
        return user_id in self._admins

    async def handle(self, msg: dict) -> None:
        text = msg.get("text") or msg.get("caption") or ""
        if not text.startswith("/"):
            return
        chat_id = int(msg["chat"]["id"])
        if chat_id != self.chat_id and msg["chat"].get("type") != "private":
            return
        first, *args = text.split()
        name, _, addressed_to = first.partition("@")
        if addressed_to and self.bot_username and addressed_to.lower() != self.bot_username.lower():
            return
        name = name.lower()
        if name in ("/start", "/help"):
            await self.tg.send_text(chat_id, HELP)
            return
        if not await self.is_admin(int(msg.get("from", {}).get("id", 0))):
            return
        if not name[1:].isalnum():
            return
        handler = getattr(self, "cmd_" + name[1:], None)
        if handler is None:
            return
        reply = await handler(args, msg.get("reply_to_message"), msg)
        if reply:
            await self.tg.send_text(chat_id, reply)
        self.st.save(self.path)
