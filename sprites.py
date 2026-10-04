"""Sprite format helpers: validate, repair, slug, preview image, LED drawing.

On-disk sprite format (art/*.json):
    {"name": str, "palette": {"k": [0,0,0], ...}, "fps": int,
     "frames": [[16 strings of 16 chars], ...]}
"""
import hashlib
import json
import os
import re
from pathlib import Path

from PIL import Image

SIZE = 16
MAX_COLOURS = 8
MAX_FRAMES = 4
BLACK = "k"

ROOT = Path(__file__).resolve().parent
ART_DIR = ROOT / "art"
STATE_FILE = ROOT / "state.json"


def validate(data):
    """Raise ValueError if the sprite doesn't match the format exactly."""
    pal = data.get("palette")
    if not isinstance(pal, dict) or not 1 <= len(pal) <= MAX_COLOURS:
        raise ValueError(f"palette must have 1-{MAX_COLOURS} colours")
    for key, rgb in pal.items():
        if len(key) != 1:
            raise ValueError(f"palette key {key!r} must be a single character")
        if len(rgb) != 3 or not all(isinstance(c, int) and 0 <= c <= 255 for c in rgb):
            raise ValueError(f"palette colour {key!r} must be 3 ints 0-255")
    frames = data.get("frames")
    if not isinstance(frames, list) or not 1 <= len(frames) <= MAX_FRAMES:
        raise ValueError(f"need 1-{MAX_FRAMES} frames")
    for i, frame in enumerate(frames):
        if len(frame) != SIZE:
            raise ValueError(f"frame {i} has {len(frame)} rows, need {SIZE}")
        for y, row in enumerate(frame):
            if len(row) != SIZE:
                raise ValueError(f"frame {i} row {y} has {len(row)} chars, need {SIZE}")
            bad = set(row) - set(pal)
            if bad:
                raise ValueError(f"frame {i} row {y} uses unknown chars {sorted(bad)}")
    return data


def repair(data):
    """Fix the small mistakes models make (row off by a char or two, stray chars).

    Returns (sprite, notes). Raises ValueError for anything too broken to patch,
    so the caller can retry with the error.
    """
    notes = []
    pal = {k: [max(0, min(255, int(c))) for c in rgb] for k, rgb in data["palette"].items()}
    if len(pal) > MAX_COLOURS:
        raise ValueError(f"palette has {len(pal)} colours, max is {MAX_COLOURS}")
    if pal.get(BLACK) != [0, 0, 0]:
        pal[BLACK] = [0, 0, 0]
        notes.append("forced 'k' to black")

    frames = data["frames"][:MAX_FRAMES]
    if not frames:
        raise ValueError("no frames")
    fixed_frames = []
    for i, frame in enumerate(frames):
        if abs(len(frame) - SIZE) > 2:
            raise ValueError(f"frame {i} has {len(frame)} rows, need exactly {SIZE}")
        if len(frame) != SIZE:
            notes.append(f"frame {i}: {len(frame)} rows padded/trimmed to {SIZE}")
        frame = (list(frame) + [BLACK * SIZE] * SIZE)[:SIZE]
        rows = []
        for y, row in enumerate(frame):
            if abs(len(row) - SIZE) > 2:
                raise ValueError(f"frame {i} row {y} has {len(row)} chars, need exactly {SIZE}")
            if len(row) != SIZE:
                notes.append(f"frame {i} row {y}: {len(row)} chars")
            row = "".join(ch if ch in pal else BLACK for ch in row)
            rows.append((row + BLACK * SIZE)[:SIZE])
        fixed_frames.append(rows)

    sprite = {
        "name": data.get("name", ""),
        "palette": pal,
        "fps": max(1, min(12, int(data.get("fps", 4)))),
        "frames": fixed_frames,
    }
    return validate(sprite), notes


def slug(prompt):
    s = re.sub(r"[^a-z0-9]+", "-", prompt.lower()).strip("-")[:40]
    return s or hashlib.sha1(prompt.encode()).hexdigest()[:10]


def load(path):
    with open(path, encoding="utf-8") as f:
        return validate(json.load(f))


def write_json(path, data):
    """Write atomically so the display never reads a half-written file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1)
    os.replace(tmp, path)


def to_image(sprite, frame=0, scale=20):
    """Upscaled preview of one frame (raw palette, no LED correction)."""
    img = Image.new("RGB", (SIZE, SIZE))
    pal = sprite["palette"]
    img.putdata([tuple(pal[ch]) for row in sprite["frames"][frame] for ch in row])
    return img.resize((SIZE * scale, SIZE * scale), Image.NEAREST)


def correct(rgb, gamma=2.0, boost=1.0):
    """LEDs are linear, so mid tones look washed out; gamma pulls them back."""
    return tuple(min(255, int(255 * ((c / 255) ** gamma) * boost)) for c in rgb)


def draw(unicornhathd, frame, palette, gamma=2.0, boost=1.0):
    lut = {ch: correct(rgb, gamma, boost) for ch, rgb in palette.items()}
    for y, row in enumerate(frame):
        for x, ch in enumerate(row):
            unicornhathd.set_pixel(x, y, *lut[ch])
    unicornhathd.show()
