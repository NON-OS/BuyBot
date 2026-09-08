#!/usr/bin/env python3
"""Build the NOX premium (custom) emoji and optionally publish it as a custom
emoji pack owned by you, via the Bot API.

    /usr/bin/python3 tools/make_emoji.py                 # writes media/emoji-nox.png (100x100)
    /usr/bin/python3 tools/make_emoji.py --create --owner <your_telegram_user_id>

After --create the script prints the custom_emoji_id. Set it in the group with
/setemoji by replying to a message containing the emoji, or paste the id into
state.json -> settings.custom_emoji_id.

Telegram rule to know: a bot can only *send* custom emoji if it owns a
collectible username bought on Fragment. Without it the bot silently falls back
to the standard emoji; premium members of the group can still use the pack.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import urllib.request
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
MEDIA = ROOT / "media"
TEAL = (87, 239, 224)


def render(px: int = 100) -> Path:
    out = MEDIA / "emoji-nox.png"
    svg = MEDIA / "nox-logo.svg"
    if svg.exists() and shutil.which("rsvg-convert"):
        tmp = MEDIA / ".emoji.svg"
        tmp.write_text(svg.read_text().replace('fill="currentColor"', f'fill="rgb{TEAL}"'))
        subprocess.run(["rsvg-convert", "-h", str(px), "-o", str(out), str(tmp)], check=True)
        tmp.unlink()
        img = Image.open(out).convert("RGBA")
    else:
        img = Image.open(MEDIA / "nox-badge.png").convert("RGBA")
        img = img.resize((int(px * img.width / img.height), px), Image.LANCZOS)
    canvas = Image.new("RGBA", (px, px), (0, 0, 0, 0))
    canvas.alpha_composite(img, ((px - img.width) // 2, (px - img.height) // 2))
    canvas.save(out, optimize=True)
    print(f"wrote {out} ({canvas.size[0]}x{canvas.size[1]})")
    return out


def api(token: str, method: str, fields: dict, files: dict | None = None) -> dict:
    boundary = "----noxbuybot"
    body = bytearray()
    for k, v in fields.items():
        body += f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"\r\n\r\n".encode()
        body += (json.dumps(v) if isinstance(v, (dict, list)) else str(v)).encode() + b"\r\n"
    for k, p in (files or {}).items():
        body += f"--{boundary}\r\nContent-Disposition: form-data; name=\"{k}\"; filename=\"{p.name}\"\r\nContent-Type: image/png\r\n\r\n".encode()
        body += p.read_bytes() + b"\r\n"
    body += f"--{boundary}--\r\n".encode()
    req = urllib.request.Request(
        f"https://api.telegram.org/bot{token}/{method}", data=bytes(body),
        headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
    )
    with urllib.request.urlopen(req, timeout=60) as resp:
        res = json.load(resp)
    if not res.get("ok"):
        sys.exit(f"{method}: {res}")
    return res["result"]


def create(token: str, owner: int, png: Path, name_suffix: str) -> None:
    me = api(token, "getMe", {})
    set_name = f"nox_{name_suffix}_by_{me['username']}"
    uploaded = api(token, "uploadStickerFile", {"user_id": owner, "sticker_format": "static"}, {"sticker": png})
    sticker = {"sticker": uploaded["file_id"], "format": "static", "emoji_list": ["🟢"], "keywords": ["nox", "buy"]}
    try:
        api(token, "createNewStickerSet", {
            "user_id": owner, "name": set_name, "title": "NOX", "sticker_type": "custom_emoji", "stickers": [sticker],
        })
        print(f"created custom emoji pack t.me/addemoji/{set_name}")
    except SystemExit as exc:
        if "STICKERSET_INVALID" in str(exc) or "already occupied" in str(exc):
            api(token, "addStickerToSet", {"user_id": owner, "name": set_name, "sticker": sticker})
            print(f"added to existing pack t.me/addemoji/{set_name}")
        else:
            raise
    pack = api(token, "getStickerSet", {"name": set_name})
    for s in pack["stickers"]:
        print("custom_emoji_id:", s.get("custom_emoji_id"))


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--create", action="store_true", help="publish as a custom emoji pack via the Bot API")
    ap.add_argument("--owner", type=int, help="Telegram user id that will own the pack")
    ap.add_argument("--suffix", default="logo", help="pack name suffix (letters/digits/underscore)")
    a = ap.parse_args()
    png = render()
    if a.create:
        token = os.environ.get("BOT_TOKEN") or _dotenv_token()
        if not token or not a.owner:
            sys.exit("--create needs BOT_TOKEN (env or .env) and --owner <user_id>")
        create(token, a.owner, png, a.suffix)


def _dotenv_token() -> str:
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text().splitlines():
            if line.startswith("BOT_TOKEN="):
                return line.split("=", 1)[1].strip().strip('"')
    return ""


if __name__ == "__main__":
    main()
