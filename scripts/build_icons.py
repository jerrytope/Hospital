"""Build templates/includes/icon_sprite.html from Lucide (ISC licence) SVG files."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SRC = ROOT / "node_modules" / "lucide-static" / "icons"
OUT = ROOT / "templates" / "includes" / "icon_sprite.html"

ICONS = """heart-pulse stethoscope baby droplets wheat brain users hospital syringe shield-alert tent truck
graduation-cap hand-heart globe map-pin activity pill apple house flame cloud-rain bug swords siren ambulance
search x menu chevron-down chevron-right chevron-left arrow-right facebook instagram linkedin youtube mail phone
printer file-text download copy check calendar clock play gift heart user log-out lock external-link share-2
book-open microscope handshake megaphone briefcase scale leaf sun mountain waves""".split()

symbols = []
for name in ICONS:
    svg = (SRC / f"{name}.svg").read_text(encoding="utf-8")
    inner = re.search(r"<svg[^>]*>(.*)</svg>", svg, re.S).group(1).strip()
    inner = re.sub(r"\s+", " ", inner)
    symbols.append(f'<symbol id="i-{name}" viewBox="0 0 24 24">{inner}</symbol>')

# X (formerly Twitter) mark, drawn as a simple stroked glyph.
symbols.append('<symbol id="i-x-social" viewBox="0 0 24 24"><path d="M4 4l16 16M20 4L4 20" /></symbol>')

OUT.write_text(
    '<svg xmlns="http://www.w3.org/2000/svg" style="display:none" fill="none" stroke="currentColor" '
    'stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">\n'
    + "\n".join(symbols)
    + "\n</svg>\n",
    encoding="utf-8",
)
print(f"wrote {len(symbols)} icons to {OUT.relative_to(ROOT)}")
