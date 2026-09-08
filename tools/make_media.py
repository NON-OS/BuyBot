#!/usr/bin/env python3
"""Generate the four tiered buy animations (small/medium/large/whale) from the
NOX logo. Output: media/buy-<tier>.gif and, when ffmpeg is present, .mp4.

    /usr/bin/python3 tools/make_media.py [--size 512] [--frames 36] [--fps 18]
"""
from __future__ import annotations

import argparse
import math
import random
import shutil
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

ROOT = Path(__file__).resolve().parent.parent
MEDIA = ROOT / "media"
TEAL = (87, 239, 224)
BG = (7, 11, 16)
WHITE = (240, 250, 250)

FONT_CANDIDATES = [
    "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
]


def font(size: int) -> ImageFont.ImageFont:
    for p in FONT_CANDIDATES:
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                continue
    return ImageFont.load_default()


def render_logo(px: int) -> Image.Image:
    """Rasterise nox-logo.svg in brand teal; falls back to the bundled badge PNG."""
    svg = MEDIA / "nox-logo.svg"
    out = MEDIA / f".logo-{px}.png"
    if svg.exists() and shutil.which("rsvg-convert"):
        tinted = svg.read_text().replace('fill="currentColor"', f'fill="rgb{TEAL}"')
        tmp = MEDIA / ".logo-tinted.svg"
        tmp.write_text(tinted)
        subprocess.run(["rsvg-convert", "-h", str(px), "-o", str(out), str(tmp)], check=True)
        tmp.unlink()
        img = Image.open(out).convert("RGBA")
        out.unlink()
        return img
    img = Image.open(MEDIA / "nox-badge.png").convert("RGBA")
    return img.resize((int(px * img.width / img.height), px), Image.LANCZOS)


def glow(size: int, radius: int, color: tuple, alpha: int) -> Image.Image:
    layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(layer)
    c = size // 2
    d.ellipse((c - radius, c - radius, c + radius, c + radius), fill=color + (alpha,))
    return layer.filter(ImageFilter.GaussianBlur(radius // 2))


def base_frame(size: int) -> Image.Image:
    img = Image.new("RGBA", (size, size), BG + (255,))
    d = ImageDraw.Draw(img)
    step = size // 12
    for i in range(0, size, step):
        d.line((i, 0, i, size), fill=(14, 22, 30, 255))
        d.line((0, i, size, i), fill=(14, 22, 30, 255))
    return img


def paste_center(img: Image.Image, layer: Image.Image, cx: int, cy: int) -> None:
    img.alpha_composite(layer, (int(cx - layer.width / 2), int(cy - layer.height / 2)))


def label(img: Image.Image, text: str, y: int, size: int, color=WHITE) -> None:
    d = ImageDraw.Draw(img)
    f = font(size)
    w = d.textlength(text, font=f)
    d.text(((img.width - w) / 2, y), text, font=f, fill=color)


class Particles:
    def __init__(self, n: int, size: int, seed: int, speed: float, spread: float = 1.0):
        rnd = random.Random(seed)
        self.size = size
        self.p = [
            (rnd.random() * size, rnd.random() * size, rnd.uniform(0.4, 1.0), rnd.uniform(2, 6) * spread)
            for _ in range(n)
        ]
        self.speed = speed

    def draw(self, img: Image.Image, t: float, color=TEAL) -> None:
        d = ImageDraw.Draw(img)
        for x, y0, v, r in self.p:
            y = (y0 - t * self.speed * v * self.size) % self.size
            a = int(255 * (0.3 + 0.7 * v))
            d.ellipse((x - r, y - r, x + r, y + r), fill=color + (a,))


def frames_small(size: int, n: int, logo: Image.Image) -> list[Image.Image]:
    out = []
    for i in range(n):
        t = i / n
        img = base_frame(size)
        pulse = 1 + 0.06 * math.sin(2 * math.pi * t)
        img.alpha_composite(glow(size, int(size * 0.28 * pulse), TEAL, 90))
        lg = logo.resize((int(logo.width * pulse), int(logo.height * pulse)), Image.LANCZOS)
        paste_center(img, lg, size // 2, int(size * 0.46))
        label(img, "NOX BUY", int(size * 0.84), size // 11, TEAL)
        out.append(img.convert("P", palette=Image.ADAPTIVE, colors=128))
    return out


def frames_medium(size: int, n: int, logo: Image.Image) -> list[Image.Image]:
    parts = Particles(40, size, 7, 0.9)
    out = []
    for i in range(n):
        t = i / n
        img = base_frame(size)
        parts.draw(img, t)
        pulse = 1 + 0.1 * math.sin(2 * math.pi * t)
        img.alpha_composite(glow(size, int(size * 0.32 * pulse), TEAL, 120))
        lg = logo.resize((int(logo.width * pulse), int(logo.height * pulse)), Image.LANCZOS)
        paste_center(img, lg, size // 2, int(size * 0.46))
        label(img, "NOX BUY", int(size * 0.84), size // 10, TEAL)
        out.append(img.convert("P", palette=Image.ADAPTIVE, colors=128))
    return out


def frames_large(size: int, n: int, logo: Image.Image) -> list[Image.Image]:
    lines = Particles(70, size, 11, 2.4, spread=0.5)
    flame = Particles(60, size, 13, 1.6)
    out = []
    for i in range(n):
        t = i / n
        img = base_frame(size)
        lines.draw(img, t, color=(120, 160, 170))
        # rocket lift: logo eases up, overshoots, settles
        lift = math.sin(min(1.0, t * 1.3) * math.pi / 2) * size * 0.18
        shake = math.sin(t * 40) * size * 0.006
        cy = int(size * 0.55 - lift)
        img.alpha_composite(glow(size, int(size * 0.36), (255, 140, 60), 70).crop((0, 0, size, size)).transform(
            (size, size), Image.AFFINE, (1, 0, 0, 0, 1, -(cy - size // 2) - size * 0.22)))
        flame_layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        flame.draw(flame_layer, t, color=(255, 150, 60))
        mask = Image.new("L", (size, size), 0)
        ImageDraw.Draw(mask).rectangle((size * 0.3, cy + logo.height * 0.45, size * 0.7, size), fill=255)
        img.alpha_composite(Image.composite(flame_layer, Image.new("RGBA", (size, size), (0, 0, 0, 0)), mask))
        img.alpha_composite(glow(size, int(size * 0.3), TEAL, 110).transform(
            (size, size), Image.AFFINE, (1, 0, 0, 0, 1, -(cy - size // 2))))
        paste_center(img, logo, size // 2 + int(shake), cy)
        label(img, "BIG BUY", int(size * 0.84), size // 8, TEAL)
        out.append(img.convert("P", palette=Image.ADAPTIVE, colors=128))
    return out


def frames_whale(size: int, n: int, logo: Image.Image) -> list[Image.Image]:
    spray = Particles(50, size, 17, 1.2)
    out = []
    for i in range(n):
        t = i / n
        img = base_frame(size)
        d = ImageDraw.Draw(img)
        # layered waves
        for k, (amp, col, base) in enumerate([(14, (16, 80, 120), 0.74), (18, (20, 120, 160), 0.80), (12, (87, 239, 224), 0.86)]):
            pts = [(x, size * base + amp * math.sin(2 * math.pi * (x / size * 2 + t + k * 0.3))) for x in range(0, size + 8, 8)]
            d.polygon(pts + [(size, size), (0, size)], fill=col + (255,))
        spray_layer = Image.new("RGBA", (size, size), (0, 0, 0, 0))
        spray.draw(spray_layer, t, color=(200, 245, 255))
        img.alpha_composite(spray_layer)
        bob = math.sin(2 * math.pi * t) * size * 0.03
        img.alpha_composite(glow(size, int(size * 0.34), TEAL, 130))
        big = logo.resize((int(logo.width * 1.15), int(logo.height * 1.15)), Image.LANCZOS)
        paste_center(img, big, size // 2, int(size * 0.42 + bob))
        label(img, "WHALE BUY", int(size * 0.06), size // 8, WHITE)
        out.append(img.convert("P", palette=Image.ADAPTIVE, colors=128))
    return out


BUILDERS = {"small": frames_small, "medium": frames_medium, "large": frames_large, "whale": frames_whale}


def save(frames: list[Image.Image], name: str, fps: int) -> None:
    gif = MEDIA / f"buy-{name}.gif"
    frames[0].save(gif, save_all=True, append_images=frames[1:], duration=int(1000 / fps), loop=0, optimize=True)
    print(f"wrote {gif} ({gif.stat().st_size // 1024} KB)")
    if shutil.which("ffmpeg"):
        mp4 = MEDIA / f"buy-{name}.mp4"
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", str(gif), "-movflags", "faststart", "-pix_fmt", "yuv420p",
             "-vf", "scale=trunc(iw/2)*2:trunc(ih/2)*2", "-an", str(mp4)],
            check=True,
        )
        print(f"wrote {mp4} ({mp4.stat().st_size // 1024} KB)")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--size", type=int, default=512)
    ap.add_argument("--frames", type=int, default=36)
    ap.add_argument("--fps", type=int, default=18)
    ap.add_argument("--only", choices=list(BUILDERS), action="append")
    a = ap.parse_args()
    logo = render_logo(int(a.size * 0.42))
    for name, build in BUILDERS.items():
        if a.only and name not in a.only:
            continue
        save(build(a.size, a.frames, logo), name, a.fps)


if __name__ == "__main__":
    main()
