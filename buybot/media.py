from __future__ import annotations

from pathlib import Path

KIND_BY_EXT = {
    ".gif": "animation", ".mp4": "animation",
    ".webp": "photo", ".png": "photo", ".jpg": "photo", ".jpeg": "photo",
    ".webm": "sticker", ".tgs": "sticker",
}
METHOD = {"animation": "sendAnimation", "photo": "sendPhoto", "video": "sendVideo", "sticker": "sendSticker"}
FIELD = {"animation": "animation", "photo": "photo", "video": "video", "sticker": "sticker"}
MAX_UPLOAD_BYTES = 50 * 1024 * 1024


def media_kind_for(path: Path) -> str:
    return KIND_BY_EXT.get(path.suffix.lower(), "photo")


def media_from_message(msg: dict) -> tuple[str, str] | None:
    if "animation" in msg:
        return "animation", msg["animation"]["file_id"]
    if "video" in msg:
        return "video", msg["video"]["file_id"]
    if "sticker" in msg:
        return "sticker", msg["sticker"]["file_id"]
    if "photo" in msg:
        return "photo", msg["photo"][-1]["file_id"]
    if "document" in msg and msg["document"].get("mime_type") in ("image/gif", "video/mp4"):
        return "animation", msg["document"]["file_id"]
    return None
