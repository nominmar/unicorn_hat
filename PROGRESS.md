# Progress

Where the Unicorn desk display is at, so work can pick up later. The full plan is in `unicorn-plan.md`.

_Last updated: 2026-10-04_

## Resume here

1. **Commit and push the systemd files.** `deploy/` is untracked, and commit `8a72a3b` (shutdown button) is not pushed yet:
   ```
   git add deploy PROGRESS.md && git commit -m "Add systemd services and progress notes" && git push
   ```
2. **Install the services on the Pi** (not done yet):
   ```bash
   cd ~/unicorn
   mv art/cat.json art/cat-pi.json     # the repo now has its own art/cat.json; otherwise the pull fails
   git pull
   pkill -f display.py; pkill -f streamlit
   sudo nano /etc/unicorn.env          # one line: ANTHROPIC_API_KEY=sk-ant-...  (no "export", no quotes)
   sudo chmod 600 /etc/unicorn.env
   sudo cp deploy/*.service /etc/systemd/system/
   sudo systemctl daemon-reload
   sudo systemctl enable --now unicorn-display unicorn-ui
   systemctl status unicorn-display unicorn-ui
   ```
3. **Test a power cycle:** in the app, open Power → Shut down Pi, unplug, then plug back in. The last sprite and the web app should come back on their own.
   - If the button says `sudo: a password is required`, the user needs a sudoers rule that allows only `shutdown`.
4. **Then start Phase 5 (markets).** See "Next" below.

## Done

| Phase | What | Status |
|---|---|---|
| 0–1 | Pi set up, SPI on, Python environment at `~/unicorn-env`, LEDs work | Done |
| 2 | `sprites.py`: format, validation, auto-repair, gamma correction, preview image | Done |
| 3 | `display.py`: watches `state.json`, draws and animates sprites, LEDs off on exit | Working on the Pi |
| 4 | `llm.py`: word → Claude → 16×16 sprite, one retry, cached in `art/` | Working on the Pi |
| 6 (partial) | `app.py`: Generate shows straight on the display, gallery, brightness, On/Off, Preview and Power sections | Working on the Pi |
| 7 | `deploy/*.service` + Shut down button | Written, **not installed yet** |

Extras:
- **Custom words:** the `CUSTOM` dict in `llm.py`. "Nomin" maps to a winking anime girl with brown hair and a twinkling star. Not generated yet.
- **Diagram for Instagram:** hand-drawn flowchart plus hardware sketch at https://claude.ai/artifact/DURCbxL1PWzTqXpAtzCfcZ (private).

## Setup facts

- **Pi:** hostname `unicorn`, user `nmargade`, IP `192.168.1.100` (reserving it in the router is still to do). App at http://192.168.1.100:8501
- **Paths on the Pi:** code in `~/unicorn`, Python environment in `~/unicorn-env`, API key in `/etc/unicorn.env` (for systemd) and `~/.bashrc` (for manual runs)
- **GitHub:** `nominmar/unicorn_hat` (private), branch `main`. The Pi clones over HTTPS with a fine-grained token (Contents: Read-only).
- **Model:** `claude-opus-5-5` with `EFFORT = "low"`, set in `llm.py`

## Lessons so far

- **`art/` is tracked in git now; `state.json` is still gitignored.** Sprites committed from the PC reach the Pi on `git pull`. Sprites generated on the Pi stay untracked there. If a pull says "untracked working tree files would be overwritten" (e.g. `art/cat.json` exists on both sides), move the Pi's copy aside first: `mv art/cat.json art/cat-pi.json`.
- **"Could not resolve authentication method"** means the Streamlit process can't see `ANTHROPIC_API_KEY`. Usually an old process started without it is still running: `pkill -f streamlit` and start again.
- **`display.py` prints nothing until `state.json` exists.** That's expected, not a hang.
- **GitHub tokens:** fine-grained tokens need Contents: Read-only, or the clone fails with a misleading "Write access not granted" error.
- **Sprite quality:** the first cat was ugly. If the results stay poor: raise `EFFORT` to `"medium"`, add outline/style hints to `SYSTEM`, or include an example sprite in the prompt.

## Next

1. **Phase 5: Markets.** Write `markets.py` (yfinance prices, FRED yield curve, rocket/crying rules, sparkline). Add `stock` / `yield` / `rotate` modes to `display.py` and a Markets tab to `app.py`. Poll at most every 5 minutes, and cache results.
2. **`builtin/` sprites:** rocket, crying face, neutral. These are needed by the market rules.
3. **Nice-to-haves:**
   - Tailscale, to use the app away from home
   - Add the phone hotspot as a saved Wi-Fi network on the Pi
   - Reserve the Pi's IP in the router
   - Clock mode when idle
   - Print `waiting for state.json` at startup in `display.py`
