"""Environment configuration, validated at start so a bad deployment fails
immediately instead of at the first buy."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

NOX_TOKEN = "0x0a26c80Be4E060e688d7C23aDdB92cBb5D2C9eCA"
NOX_WETH_V2_PAIR = "0x07CE5889D2EB681Af3bD61db24Ab2602c502Bd1B"
WETH = "0xC02aaA39b223FE8D0A0e5C4F27eAD9083C756Cc2"
CHAINLINK_ETH_USD = "0x5f4eC3Df9cbd43714FE2740f5E3616155c5b8419"

ADDRESS_RE = re.compile(r"^0x[0-9a-fA-F]{40}$")
BOT_TOKEN_RE = re.compile(r"^\d{6,12}:[A-Za-z0-9_-]{30,}$")


class ConfigError(SystemExit):
    def __init__(self, message: str):
        super().__init__(f"config: {message}")


def _load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        value = value.split(" #", 1)[0].strip().strip('"').strip("'")
        os.environ.setdefault(key.strip(), value)


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _env_int(name: str, default: int, lo: int, hi: int) -> int:
    raw = _env(name)
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        raise ConfigError(f"{name} must be an integer") from None
    if not lo <= value <= hi:
        raise ConfigError(f"{name} must be between {lo} and {hi}")
    return value


def _env_float(name: str, default: float, lo: float, hi: float) -> float:
    raw = _env(name)
    if not raw:
        return default
    try:
        value = float(raw)
    except ValueError:
        raise ConfigError(f"{name} must be a number") from None
    if not lo <= value <= hi:
        raise ConfigError(f"{name} must be between {lo} and {hi}")
    return value


def _env_ids(name: str) -> list[int]:
    raw = _env(name)
    out = []
    for part in raw.replace(";", ",").split(","):
        part = part.strip()
        if not part:
            continue
        if not part.lstrip("-").isdigit():
            raise ConfigError(f"{name} contains a non-numeric id: {part!r}")
        out.append(int(part))
    return out


def _env_address(name: str, default: str) -> str:
    value = _env(name, default)
    if not ADDRESS_RE.match(value):
        raise ConfigError(f"{name} is not a 20-byte hex address")
    return value


def _env_url(name: str, schemes: tuple[str, ...], required: bool) -> str:
    value = _env(name)
    if not value:
        if required:
            raise ConfigError(f"{name} is required")
        return ""
    if not value.lower().startswith(tuple(s + "://" for s in schemes)):
        raise ConfigError(f"{name} must start with one of {', '.join(s + '://' for s in schemes)}")
    return value


@dataclass
class Config:
    bot_token: str
    chat_id: int
    rpc_http: str
    rpc_ws: str
    token: str = NOX_TOKEN
    pair: str = NOX_WETH_V2_PAIR
    weth: str = WETH
    eth_usd_feed: str = CHAINLINK_ETH_USD
    admin_ids: list[int] = field(default_factory=list)
    confirmations: int = 0
    poll_seconds: float = 4.0
    state_file: Path = ROOT / "state.json"
    media_dir: Path = ROOT / "media"
    log_level: str = "INFO"
    symbol: str = "NOX"
    chain_slug: str = "ethereum"
    website: str = "https://nonos.software"

    @classmethod
    def from_env(cls) -> Config:
        _load_dotenv(ROOT / ".env")
        token = _env("BOT_TOKEN")
        if not BOT_TOKEN_RE.match(token):
            raise ConfigError("BOT_TOKEN missing or malformed (expected <id>:<secret> from @BotFather)")
        chat = _env("CHAT_ID")
        if not chat.lstrip("-").isdigit():
            raise ConfigError("CHAT_ID must be the numeric group id (supergroups start with -100)")
        level = _env("LOG_LEVEL", "INFO").upper()
        if level not in ("DEBUG", "INFO", "WARNING", "ERROR"):
            raise ConfigError("LOG_LEVEL must be DEBUG, INFO, WARNING or ERROR")
        website = _env("WEBSITE", "https://nonos.software")
        if not website.lower().startswith(("https://", "http://")):
            raise ConfigError("WEBSITE must be an http(s) URL")
        return cls(
            bot_token=token,
            chat_id=int(chat),
            rpc_http=_env_url("RPC_HTTP", ("https", "http"), required=True),
            rpc_ws=_env_url("RPC_WS", ("wss", "ws"), required=False),
            token=_env_address("TOKEN_ADDRESS", NOX_TOKEN),
            pair=_env_address("PAIR_ADDRESS", NOX_WETH_V2_PAIR),
            admin_ids=_env_ids("ADMIN_IDS"),
            confirmations=_env_int("CONFIRMATIONS", 0, 0, 64),
            poll_seconds=_env_float("POLL_SECONDS", 4.0, 1.0, 120.0),
            state_file=Path(_env("STATE_FILE", str(ROOT / "state.json"))),
            media_dir=Path(_env("MEDIA_DIR", str(ROOT / "media"))),
            log_level=level,
            website=website,
        )
