# Unicorn Desk Display: Project Plan

A Raspberry Pi 4 + Unicorn HAT HD (16×16 RGB LEDs) that shows:

1. **LLM pixel art:** type a word in a web UI, Claude returns a 16×16 sprite as JSON, the LEDs draw it
2. **Market mood display:** ticker rules (rocket / crying face) plus a sparkline
3. **Yield curve:** 16 bars, red when inverted
4. *(Stretch)* PC music visualiser over UDP

```
Phone/PC browser ──► Streamlit UI ──► Claude API ──► JSON frames
                          │                              │
                          ▼                              ▼
                   state.json / art/*.json  ◄────────────┘
                          │
                          ▼
                  Display daemon ──► unicornhathd ──► LEDs
```

**Key rule:** only the daemon touches the LEDs. Streamlit reruns its script on every interaction, so drawing from it would make the display stutter. The two talk through files.

---

## 1. Hardware / Software

| Item | Notes |
|---|---|
| Raspberry Pi 4B 4GB | Heatsink + official case (lid off or HAT on top) |
| Unicorn HAT HD | Attach with Pi **powered off** |
| microSD 32GB | Flash with Raspberry Pi Imager |
| OS | Raspberry Pi OS Lite 64-bit |
| Python libs | `unicornhathd`, `streamlit`, `anthropic`, `yfinance`, `requests`, `numpy`, `pillow` |

---

## 2. Phase 0: Setup

- [ ] Flash SD with Imager: Pi 4, OS Lite 64-bit, *Edit Settings* → hostname `unicorn`, username/password, Wi-Fi + country, **enable SSH**
- [ ] Insert card, attach HAT (unplugged), power on, wait 2-3 min
- [ ] `ssh <user>@unicorn.local` (or use the IP from your router)
- [ ] `sudo raspi-config` → Interface Options → **SPI → Yes**, then reboot
- [ ] Update: `sudo apt update && sudo apt full-upgrade -y`
- [ ] Create venv (needed on Bookworm, pip refuses system-wide installs):

```bash
sudo apt install -y python3-venv python3-dev python3-pil python3-numpy git
python3 -m venv --system-site-packages ~/unicorn-env
source ~/unicorn-env/bin/activate
pip install unicornhathd streamlit anthropic yfinance requests
```

- [ ] Optional: DHCP reservation in your router so the Pi keeps a fixed IP

---

## 3. Phase 1: Hello LEDs

Goal: confirm wiring, SPI and power are all fine.

```python
# test.py
import unicornhathd, time
unicornhathd.rotation(0)
unicornhathd.brightness(0.5)
for x in range(16):
    for y in range(16):
        unicornhathd.set_pixel(x, y, x * 16, y * 16, 128)
unicornhathd.show()
time.sleep(5)
unicornhathd.off()
```

- [ ] Run it, get a colour gradient
- [ ] Adjust `rotation()` until the image is the right way up for how the Pi sits on your desk
- [ ] Try Pimoroni's bundled examples (clone `pimoroni/unicorn-hat-hd`, see `examples/`)

---

## 4. Phase 2: Sprite format and renderer

### JSON schema

```json
{
  "name": "rocket",
  "palette": {"k": [0,0,0], "r": [255,40,40], "w": [255,255,255]},
  "fps": 4,
  "frames": [
    ["kkkkkkkkkkkkkkkk", "...16 rows of 16 chars..."]
  ]
}
```

- Each character indexes into `palette`. Palette is limited to 8 colours.
- 1 frame = still image, 2-4 frames = looping animation.
- `k` (black) is the background.

### Files

```
unicorn/
├── daemon.py        # owns the LEDs
├── app.py           # Streamlit UI
├── sprites.py       # load, validate, render helpers
├── llm.py           # Claude call + retry + cache
├── markets.py       # yfinance + FRED + rules
├── state.json       # UI → daemon: mode, current sprite, brightness
├── art/             # generated sprites, named by slugified prompt
└── builtin/         # hand-made sprites: rocket.json, sad.json, ...
```

### `sprites.py` essentials

```python
import json, re

def validate(data):
    pal = data["palette"]
    assert 1 <= len(pal) <= 8
    for rgb in pal.values():
        assert len(rgb) == 3 and all(0 <= c <= 255 for c in rgb)
    assert 1 <= len(data["frames"]) <= 4
    for frame in data["frames"]:
        assert len(frame) == 16
        for row in frame:
            assert len(row) == 16 and all(ch in pal for ch in row)
    return data

def slug(prompt):
    return re.sub(r"[^a-z0-9]+", "-", prompt.lower()).strip("-")[:40]

def draw(unicornhathd, frame, palette, gamma=1.0, boost=1.0):
    for y, row in enumerate(frame):
        for x, ch in enumerate(row):
            r, g, b = (min(255, int(255 * ((c / 255) ** gamma) * boost))
                       for c in palette[ch])
            unicornhathd.set_pixel(x, y, r, g, b)
    unicornhathd.show()
```

- [ ] Hand-write 2 sprites (heart, rocket) and display them
- [ ] Add LED correction: LEDs wash out and dark colours vanish, so tune `gamma` (try 1.8-2.2) and saturation until it looks right

---

## 5. Phase 3: Display daemon

Loop forever, re-reading `state.json` when its mtime changes.

```json
{
  "mode": "art",
  "sprite": "art/sleepy-cat.json",
  "brightness": 0.5,
  "rotate": ["art", "stock", "yield"],
  "rotate_seconds": 30
}
```

Modes:
- `art`: show the chosen sprite (animate if multiple frames)
- `stock`: market mood display (Phase 5)
- `yield`: yield curve (Phase 5)
- `rotate`: cycle through enabled modes
- `off`: `unicornhathd.off()`

Handle `SIGTERM` cleanly so the LEDs turn off when the service stops.

- [ ] Write `daemon.py`
- [ ] Test by editing `state.json` by hand over SSH and watching the display change

---

## 6. Phase 4: Claude "draw anything"

### API setup

- Subscriptions (Pro/Max) don't include API access. Create an account at **console.anthropic.com**, add a few dollars of credit, generate a key
- Store the key outside the repo: `/etc/unicorn.env` containing `ANTHROPIC_API_KEY=sk-ant-...`, permissions `chmod 600`
- Model: a Sonnet-class model for quality, or Haiku (`claude-haiku-4-5-20251001`) for cheap and fast. Try both and compare

### `llm.py` flow

1. Slugify prompt, return cached file from `art/` if it exists
2. Call the API with the system prompt below
3. Parse JSON, run `validate()`
4. On failure, retry once, feeding back the error message
5. Save to `art/<slug>.json`, update `state.json`

### System prompt (starting point)

```
You design 16x16 pixel art for an LED matrix. Reply with JSON only, no prose,
no code fences.

Schema:
{"name": str, "palette": {"<single char>": [r,g,b], ...}, "fps": int,
 "frames": [[16 strings of exactly 16 chars], ...]}

Rules:
- Maximum 8 palette colours. "k" must be black [0,0,0] and is the background.
- Every character in every row must be a palette key.
- Use bold, simple, recognisable shapes. High contrast. Saturated colours.
  No dark greys or dim colours (they vanish on LEDs).
- Centre the subject and fill most of the grid.
- 1 frame for still objects. 2-4 frames only if motion is natural
  (blinking, flickering, bouncing).
```

### Gotchas

- Expect simple icons (hearts, faces, fruit, animals), not detail
- Models sometimes produce rows of 15 or 17 characters, so validation + retry matters
- Add a UI button to regenerate if you don't like a result

- [ ] Write `llm.py` and test from the command line before touching Streamlit
- [ ] Generate a few sprites and keep the best as `builtin/` assets (rocket, crying face, party)

---

## 7. Phase 5: Markets

### Stocks (`yfinance`, no key)

```python
import yfinance as yf
hist = yf.Ticker("NVDA").history(period="1mo", interval="1d")["Close"]
```

Rules engine, configurable from the UI:

| Rule | Example | Result |
|---|---|---|
| Down more than X% over N days | -5% / 5d | crying sprite |
| Up more than X% today | +3% | rocket sprite |
| Otherwise | | neutral sprite |

Below the sprite, draw a **sparkline**: scale the last 16 closes to rows 0-15 and light one pixel per column (or fill under the line). Colour green/red by trend.

Alternatively split the screen: top 10 rows sprite, bottom 6 rows sparkline.

### Yield curve (FRED, free API key from fred.stlouisfed.org)

Series: `DGS3MO`, `DGS2`, `DGS5`, `DGS10`, `DGS30`. Draw as bars, one per maturity (interpolate to fill 16 columns). Make the whole curve red when 2Y > 10Y (inverted), green otherwise.

### Gotchas

- `yfinance` is unofficial and rate-limits. **Poll every 5+ minutes**, cache results in a file, and fall back to the last good data on errors
- Markets are closed on weekends. Show last close, not an error
- Don't poll in the UI. Only the daemon (or a helper it calls) fetches data

- [ ] Write `markets.py` and print rule results to the terminal first
- [ ] Hook into the daemon's `stock` and `yield` modes

---

## 8. Phase 6: Streamlit UI

Three tabs:

1. **Draw:** text box + Generate button, shows a preview of the 16×16 grid (scaled up with `st.image`, nearest-neighbour), "Show on display" button, gallery of saved sprites
2. **Markets:** ticker, thresholds, lookback, enable/disable yield curve, full-resolution charts (`st.line_chart`), because 16×16 is tiny
3. **Display:** mode, brightness slider, rotation interval, rotate on/off, off button

The UI only writes `state.json` and `art/*.json`. It never imports `unicornhathd`.

Run: `streamlit run app.py --server.address 0.0.0.0 --server.port 8501`
Open from phone: `http://unicorn.local:8501` (or the Pi's IP).

**Security:** Streamlit has no login. Keep it on your home network only.

- [ ] Write `app.py`
- [ ] Add the page to your phone's home screen

---

## 9. Phase 7: Run on boot (systemd)

`/etc/systemd/system/unicorn-daemon.service`

```ini
[Unit]
Description=Unicorn display daemon
After=network-online.target

[Service]
User=<your-user>
WorkingDirectory=/home/<your-user>/unicorn
EnvironmentFile=/etc/unicorn.env
ExecStart=/home/<your-user>/unicorn-env/bin/python daemon.py
Restart=always

[Install]
WantedBy=multi-user.target
```

`/etc/systemd/system/unicorn-ui.service`: same, but:

```ini
ExecStart=/home/<your-user>/unicorn-env/bin/streamlit run app.py --server.address 0.0.0.0 --server.port 8501 --server.headless true
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now unicorn-daemon unicorn-ui
journalctl -u unicorn-daemon -f    # logs
```

- [ ] Reboot and check the display and UI come back on their own

---

## 10. Optional extras

- **Tailscale** on the Pi + phone for access away from home (don't port-forward Streamlit)
- **PC music visualiser:** on the PC, capture loopback audio (`soundcard` + `numpy` FFT), bin into 16 bands, send over UDP to the Pi. Daemon gets a `visualiser` mode that listens on a UDP port and draws 16 bouncing bars
- **Retro games:** Snake or Pong with a USB controller
- **Daily "mood" sprite:** have Claude pick a sprite from a market summary
- **Clock mode:** big pixel digits when idle
- **Calendar/weather alerts**

---

## 11. Suggested order

1. Phase 0 + 1: lit LEDs (first hour)
2. Phase 2 + 3: hand-made sprites via daemon
3. Phase 4: Claude drawing from the command line
4. Phase 6: Streamlit UI (Draw tab first)
5. Phase 5: markets
6. Phase 7: systemd
7. Extras

Get each step working on its own before layering the next.

---

## 12. Troubleshooting

| Problem | Try |
|---|---|
| `ssh` can't find `unicorn.local` | Use the IP from your router; check Wi-Fi country in Imager settings; try Ethernet |
| HAT shows nothing | SPI enabled? HAT fully seated? Power supply is the official one? |
| Image upside down / mirrored | `unicornhathd.rotation(0/90/180/270)` |
| Colours look washed out | Raise gamma, boost saturation, lower brightness |
| `pip install` errors "externally managed" | Use the venv |
| Streamlit unreachable from phone | `--server.address 0.0.0.0`, same Wi-Fi, firewall off by default on Pi OS |
| LLM output fails validation | Check the retry path; tighten the prompt; try a stronger model |
| `yfinance` returns empty | Rate-limited; wait, use the cache |
