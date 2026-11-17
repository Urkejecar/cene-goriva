"""Generate the app icons (site/icon.svg, icon-180.png, icon-512.png): a white fuel drop on blue.

Run with:  .venv/Scripts/python scripts/make_icons.py
"""
from pathlib import Path

from PIL import Image, ImageDraw

SITE = Path(__file__).resolve().parent.parent / "site"
BLUE = "#2a78d6"

SVG = f"""<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100">
<rect width="100" height="100" rx="22" fill="{BLUE}"/>
<path d="M50 16 C50 16 26 44 26 60 a24 24 0 0 0 48 0 C74 44 50 16 50 16 Z" fill="#fff"/>
</svg>
"""


def drop(size: int) -> Image.Image:
    scale = 4  # draw large, then downsample for smooth edges
    s = size * scale
    img = Image.new("RGB", (s, s), BLUE)
    d = ImageDraw.Draw(img)
    u = s / 100
    # circle at the bottom of the drop
    d.ellipse([26 * u, 36 * u, 74 * u, 84 * u], fill="white")
    # tip of the drop
    d.polygon([(50 * u, 16 * u), (27.5 * u, 54 * u), (72.5 * u, 54 * u)], fill="white")
    return img.resize((size, size), Image.LANCZOS)


def main() -> None:
    (SITE / "icon.svg").write_text(SVG, encoding="utf-8", newline="\n")
    drop(180).save(SITE / "icon-180.png")
    drop(512).save(SITE / "icon-512.png")


if __name__ == "__main__":
    main()
