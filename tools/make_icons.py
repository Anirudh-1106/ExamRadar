"""Draw the app icon and write every Android size. Usage: python tools/make_icons.py

Design: a calendar page (paper) with an amber header band, on deep green, with a radar sweep in the page body:
"official dates, watched for you". Drawn in a 108-unit adaptive-icon grid; the artwork stays inside the 66-unit
safe zone so launchers can mask it to any shape.
"""

from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "apps" / "mobile" / "android" / "app" / "src" / "main" / "res"
OUT = ROOT / "docs" / "branding"

GREEN = (11, 93, 75, 255)
DEEP = (7, 61, 49, 255)
PAPER = (246, 244, 239, 255)
AMBER = (227, 155, 45, 255)
SS = 16  # supersampling factor; 1 unit = SS px at 108-unit scale before downsizing


def u(v: float) -> int:
    return round(v * SS)


def artwork(mono: bool = False) -> Image.Image:
    """108x108-unit foreground on transparent. mono=True draws a white silhouette with the radar cut out."""
    img = Image.new("RGBA", (u(108), u(108)), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    ink = (255, 255, 255, 255) if mono else PAPER
    hole = (0, 0, 0, 0)
    # page
    d.rounded_rectangle([u(30), u(31), u(78), u(80)], radius=u(7), fill=ink)
    # header band (rounded top, square bottom)
    if not mono:
        d.rounded_rectangle([u(30), u(31), u(78), u(45)], radius=u(7), fill=AMBER)
        d.rectangle([u(30), u(38), u(78), u(45)], fill=AMBER)
    else:
        d.rectangle([u(30), u(44), u(78), u(46)], fill=hole)
    # binding rings
    for x in (40, 68):
        d.rounded_rectangle([u(x - 2.2), u(26), u(x + 2.2), u(36)], radius=u(2.2), fill=hole if mono else DEEP)
    # radar scope centred in the page body: two rings, a sweep wedge, and a blip
    ox, oy, r1, r2 = 54.0, 63.0, 6.5, 13.5
    line = hole if mono else GREEN
    if not mono:
        d.pieslice([u(ox - r2), u(oy - r2), u(ox + r2), u(oy + r2)], start=285, end=345, fill=(11, 93, 75, 70))
    for r in (r1, r2):
        d.ellipse([u(ox - r), u(oy - r), u(ox + r), u(oy + r)], outline=line, width=u(2.6))
    import math

    a = math.radians(345)
    d.line([u(ox), u(oy), u(ox + r2 * math.cos(a)), u(oy + r2 * math.sin(a))], fill=line, width=u(2.6))
    d.ellipse([u(ox - 2.4), u(oy - 2.4), u(ox + 2.4), u(oy + 2.4)], fill=line)
    b = math.radians(300)
    bx, by = ox + 9.8 * math.cos(b), oy + 9.8 * math.sin(b)
    d.ellipse([u(bx - 3), u(by - 3), u(bx + 3), u(by + 3)], fill=hole if mono else AMBER)
    return img


def save(img: Image.Image, path: Path, size: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    img.resize((size, size), Image.LANCZOS).save(path, optimize=True)


def legacy(full: int = 108) -> Image.Image:
    """Square icon with rounded corners for launchers without adaptive icons (crop 76 units around the centre)."""
    base = Image.new("RGBA", (u(108), u(108)), GREEN)
    base.alpha_composite(artwork())
    crop = base.crop((u(16), u(16), u(92), u(92)))
    mask = Image.new("L", crop.size, 0)
    ImageDraw.Draw(mask).rounded_rectangle([0, 0, crop.size[0] - 1, crop.size[1] - 1], radius=round(crop.size[0] * 0.22), fill=255)
    out = Image.new("RGBA", crop.size, (0, 0, 0, 0))
    out.paste(crop, (0, 0), mask)
    return out


def notification_icon() -> Image.Image:
    """White silhouette on transparent, cropped tight (status bar icons are 24dp)."""
    m = artwork(mono=True)
    return m.crop((u(24), u(22), u(84), u(82)))


def main() -> None:
    dens = {"mdpi": 1, "hdpi": 1.5, "xhdpi": 2, "xxhdpi": 3, "xxxhdpi": 4}
    fg, mono, leg, note = artwork(), artwork(mono=True), legacy(), notification_icon()
    for name, k in dens.items():
        save(leg, RES / f"mipmap-{name}" / "ic_launcher.png", round(48 * k))
        save(fg, RES / f"mipmap-{name}" / "ic_launcher_foreground.png", round(108 * k))
        save(mono, RES / f"mipmap-{name}" / "ic_launcher_monochrome.png", round(108 * k))
        save(note, RES / f"drawable-{name}" / "ic_stat_notify.png", round(24 * k))
    (RES / "mipmap-anydpi-v26").mkdir(parents=True, exist_ok=True)
    (RES / "mipmap-anydpi-v26" / "ic_launcher.xml").write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n'
        '<adaptive-icon xmlns:android="http://schemas.android.com/apk/res/android">\n'
        '    <background android:drawable="@color/ic_launcher_background"/>\n'
        '    <foreground android:drawable="@mipmap/ic_launcher_foreground"/>\n'
        '    <monochrome android:drawable="@mipmap/ic_launcher_monochrome"/>\n'
        '</adaptive-icon>\n', encoding="utf-8")
    (RES / "values" / "colors.xml").write_text(
        '<?xml version="1.0" encoding="utf-8"?>\n<resources>\n'
        '    <color name="ic_launcher_background">#0B5D4B</color>\n'
        '    <color name="splash_background">#F6F4EF</color>\n</resources>\n', encoding="utf-8")
    OUT.mkdir(parents=True, exist_ok=True)
    play = Image.new("RGBA", (u(108), u(108)), GREEN)
    play.alpha_composite(artwork())
    save(play.crop((u(12), u(12), u(96), u(96))), OUT / "play-store-icon-512.png", 512)
    save(leg, OUT / "icon-preview-192.png", 192)
    save(leg, OUT / "icon-preview-48.png", 48)
    print("icons written")


if __name__ == "__main__":
    main()
