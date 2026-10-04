"""Word -> Claude -> 16x16 sprite JSON, cached in art/<slug>.json.

CLI test:  python llm.py cat [--force]
"""
import json
import sys

import anthropic

import sprites

MODEL = "claude-opus-5-5"   # try "claude-haiku-4-5" for speed
EFFORT = "low"              # Opus 5.5 can't disable thinking; effort is the speed knob

SYSTEM = """You design 16x16 pixel art for an RGB LED matrix.

Format:
- "palette": up to 8 entries, each a single character and an [r,g,b] colour.
  "k" must be black [0,0,0] and is the background.
- "frames": each frame is exactly 16 strings, each exactly 16 characters.
  Every character must be a palette char. Count carefully.

Style:
- Bold, simple, recognisable shapes. High contrast, saturated colours.
  No dark greys or dim colours (they vanish on LEDs).
- Centre the subject and fill most of the grid.
- 1 frame for still objects. 2-4 frames only if motion is natural
  (blinking, flickering, bouncing); then set fps (2-8)."""

# Words that get a hand-written description instead of being drawn literally.
# Keys are lowercase; matching ignores case and surrounding spaces.
CUSTOM = {
    "nomin": "a cute anime-style girl's face, chibi proportions: East Asian, "
             "warm brown hair with a fringe, big sparkly eye on one side and a "
             "winking eye (a curved line) on the other, rosy blush cheeks, small "
             "smile, and a bright yellow star beside her head. 2 frames: the star "
             "twinkles (small then large), fps 3.",
}

# Palette is a list here (strict schemas can't express arbitrary dict keys);
# it's converted to the on-disk dict form after parsing.
SCHEMA = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "palette": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "char": {"type": "string"},
                    "rgb": {"type": "array", "items": {"type": "integer"}},
                },
                "required": ["char", "rgb"],
                "additionalProperties": False,
            },
        },
        "fps": {"type": "integer"},
        "frames": {"type": "array", "items": {"type": "array", "items": {"type": "string"}}},
    },
    "required": ["name", "palette", "fps", "frames"],
    "additionalProperties": False,
}

client = anthropic.Anthropic()


def _call(word, feedback=None):
    content = f"Draw: {word}"
    if feedback:
        content += f"\n\nYour previous attempt was invalid: {feedback}. Fix it."
    response = client.beta.messages.create(
        model=MODEL,
        max_tokens=16000,
        system=SYSTEM,
        messages=[{"role": "user", "content": content}],
        output_config={"effort": EFFORT, "format": {"type": "json_schema", "schema": SCHEMA}},
        betas=["server-side-fallback-2026-07-01"],
        fallbacks="default",
    )
    if response.stop_reason == "refusal":
        raise RuntimeError(f"Claude declined to draw {word!r}")
    if response.stop_reason == "max_tokens":
        raise ValueError("response was cut off")
    text = next(b.text for b in response.content if b.type == "text")
    raw = json.loads(text)
    raw["palette"] = {p["char"]: p["rgb"] for p in raw["palette"]}
    return raw


def generate(word, force=False):
    """Return (sprite, path, notes). Uses the cache unless force=True."""
    path = sprites.ART_DIR / f"{sprites.slug(word)}.json"
    if path.exists() and not force:
        return sprites.load(path), path, ["cached"]

    subject = CUSTOM.get(word.strip().lower(), word)
    feedback = None
    for attempt in range(2):
        try:
            raw = _call(subject, feedback)
            sprite, notes = sprites.repair(raw)
            break
        except (ValueError, KeyError) as e:
            feedback = str(e)
            if attempt == 1:
                raise ValueError(f"invalid sprite after retry: {e}") from e
    if feedback:
        notes.append(f"retried after: {feedback}")
    sprite["name"] = word
    sprites.write_json(path, sprite)
    return sprite, path, notes


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if a != "--force"]
    sprite, path, notes = generate(" ".join(args) or "cat", force="--force" in sys.argv)
    print(path, notes)
    for i, frame in enumerate(sprite["frames"]):
        print(f"-- frame {i}")
        print("\n".join(row.replace("k", ".") for row in frame))
