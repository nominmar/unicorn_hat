"""The only process that touches the LEDs. Watches state.json and draws the sprite.

state.json: {"sprite": "art/cat.json" | null, "brightness": 0.5}
Run on the Pi: python display.py
"""
import json
import signal
import sys
import time

import unicornhathd

import sprites

ROTATION = 0     # 0/90/180/270: set once for how the Pi sits on your desk
GAMMA = 2.0      # tune 1.8-2.2 by eye
POLL = 0.1


def shutdown(*_):
    unicornhathd.off()
    sys.exit(0)


def read_state():
    try:
        state = json.loads(sprites.STATE_FILE.read_text(encoding="utf-8"))
        sprite = sprites.load(sprites.ROOT / state["sprite"]) if state.get("sprite") else None
        return sprite, float(state.get("brightness", 0.5))
    except (OSError, ValueError, KeyError) as e:
        print(f"bad state: {e}", flush=True)
        return None


def main():
    signal.signal(signal.SIGTERM, shutdown)
    signal.signal(signal.SIGINT, shutdown)
    unicornhathd.rotation(ROTATION)

    mtime, sprite, frame, next_frame = None, None, 0, 0.0
    while True:
        try:
            m = sprites.STATE_FILE.stat().st_mtime
        except FileNotFoundError:
            m = None
        if m != mtime:
            mtime = m
            loaded = read_state() if m else (None, 0.5)
            if loaded:
                sprite, brightness = loaded
                unicornhathd.brightness(brightness)
                frame, next_frame = 0, 0.0
                if sprite is None:
                    unicornhathd.off()
                else:
                    print(f"showing {sprite['name']}", flush=True)

        now = time.monotonic()
        if sprite and now >= next_frame:
            sprites.draw(unicornhathd, sprite["frames"][frame], sprite["palette"], gamma=GAMMA)
            if len(sprite["frames"]) > 1:
                frame = (frame + 1) % len(sprite["frames"])
                next_frame = now + 1 / sprite["fps"]
            else:
                next_frame = float("inf")  # still image: draw once
        time.sleep(POLL)


if __name__ == "__main__":
    main()
