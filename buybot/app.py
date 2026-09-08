from __future__ import annotations

import asyncio
import logging
import signal

from .chain import Chain
from .commands import Commands
from .config import Config
from .poster import Poster
from .rpc import Rpc
from .state import State
from .status import Reporter
from .swaps import Swaps
from .telegram import Telegram
from .watcher import Watcher

log = logging.getLogger("buybot")


async def preflight(cfg: Config, tg: Telegram, rpc: Rpc) -> None:
    me = await tg.me()
    chat = await tg.chat(cfg.chat_id)
    log.info("bot @%s posting to %s (%s)", me.get("username"), chat.get("title") or cfg.chat_id, chat.get("type"))
    if chat.get("type") not in ("group", "supergroup", "channel"):
        raise SystemExit("CHAT_ID is not a group, supergroup or channel")
    admins = await tg.chat_admin_ids(cfg.chat_id)
    if admins and int(me["id"]) not in admins:
        log.warning("bot is not an admin of the chat, posting may fail and pins will not work")
    if await rpc.block_number() <= 0:
        raise SystemExit("RPC returned no block number")
    if not cfg.media_dir.is_dir():
        log.warning("media dir %s missing, run tools/make_media.py", cfg.media_dir)


def install_signal_handlers(stop: asyncio.Event) -> None:
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, stop.set)
        except NotImplementedError:
            pass


async def run() -> None:
    cfg = Config.from_env()
    logging.basicConfig(level=cfg.log_level, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    stop = asyncio.Event()
    install_signal_handlers(stop)

    async with Rpc(cfg.rpc_http, cfg.rpc_ws) as rpc, Telegram(cfg.bot_token) as tg:
        await preflight(cfg, tg, rpc)
        state = State.load(cfg.state_file)
        chain = Chain(rpc, cfg.token, cfg.pair, cfg.weth, cfg.eth_usd_feed, cfg.symbol)
        poster = Poster(cfg, tg, state, chain)
        watcher = Watcher(cfg, rpc, tg, state, chain, Swaps(chain), poster)
        reporter = Reporter(rpc, tg, state, chain, lambda: poster.symbol)
        commands = Commands(tg, state, cfg.state_file, cfg.chat_id, cfg.admin_ids,
                            poster.post_sample, reporter.status, reporter.stats)

        work = asyncio.gather(watcher.run(), commands.run())
        stopper = asyncio.create_task(stop.wait())
        done, _ = await asyncio.wait({work, stopper}, return_when=asyncio.FIRST_COMPLETED)
        work.cancel()
        stopper.cancel()
        state.save(cfg.state_file)
        if work in done and not work.cancelled() and work.exception():
            raise work.exception()
        log.info("stopped")


def cli() -> None:
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass
