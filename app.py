"""Streamlit UI: type a word and it goes straight to the display.

Never touches the LEDs; it only writes art/*.json and state.json.
Run: streamlit run app.py --server.address 0.0.0.0 --server.port 8501
"""
import json
import subprocess

import streamlit as st

import llm
import sprites

st.set_page_config(page_title="Unicorn", page_icon="🦄", layout="centered")
st.title("Unicorn HAT HD")


def read_state():
    try:
        return json.loads(sprites.STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"sprite": None, "brightness": 0.5}


def show(name):
    """Point the display at art/<name>.json."""
    sprites.write_json(sprites.STATE_FILE, {"sprite": f"art/{name}.json",
                                            "brightness": st.session_state.brightness})


def on_pick():
    show(st.session_state.pick)
    st.session_state.notes = []


def on_brightness():
    state = read_state()
    state["brightness"] = st.session_state.brightness
    sprites.write_json(sprites.STATE_FILE, state)


def turn_off():
    sprites.write_json(sprites.STATE_FILE, {"sprite": None,
                                            "brightness": st.session_state.brightness})


state = read_state()
if "brightness" not in st.session_state:
    st.session_state.brightness = float(state.get("brightness", 0.5))

with st.form("draw"):
    word = st.text_input("Word", placeholder="cat, rocket, pizza...")
    c1, c2 = st.columns(2)
    gen = c1.form_submit_button("Generate", type="primary", use_container_width=True)
    regen = c2.form_submit_button("Regenerate", use_container_width=True)
if (gen or regen) and word.strip():
    with st.spinner(f"Drawing {word.strip()!r}..."):
        try:
            sprite, path, notes = llm.generate(word.strip(), force=regen)
        except Exception as e:
            st.error(str(e))
        else:
            show(path.stem)
            st.session_state.pick = path.stem
            st.session_state.notes = notes
            st.success(f"Showing {word.strip()!r}")

saved = sorted(p.stem for p in sprites.ART_DIR.glob("*.json")) if sprites.ART_DIR.exists() else []
if saved:
    if st.session_state.get("pick") not in saved:
        current = sprites.Path(state.get("sprite") or "").stem
        st.session_state.pick = current if current in saved else saved[0]
    st.selectbox("Gallery", saved, key="pick", on_change=on_pick)

c1, c2 = st.columns([3, 1], vertical_alignment="bottom")
c1.slider("Brightness", 0.1, 1.0, step=0.05, key="brightness", on_change=on_brightness)
if read_state().get("sprite"):
    c2.button("Off", on_click=turn_off, use_container_width=True)
elif saved:
    c2.button("On", on_click=on_pick, use_container_width=True)

if saved:
    with st.expander("Preview"):
        sprite = sprites.load(sprites.ART_DIR / f"{st.session_state.pick}.json")
        n = len(sprite["frames"])
        st.image([sprites.to_image(sprite, i) for i in range(n)],
                 caption=[f"frame {i}" for i in range(n)] if n > 1 else None)
        if st.session_state.get("notes"):
            st.caption(" · ".join(st.session_state.notes))

with st.expander("Power"):
    st.caption("Shut down before unplugging, so the SD card doesn't get corrupted.")
    if st.button("Shut down Pi", use_container_width=True):
        try:
            r = subprocess.run(["sudo", "-n", "shutdown", "-h", "now"], capture_output=True, text=True)
            err = (r.stderr.strip() or f"exit code {r.returncode}") if r.returncode else None
        except OSError as e:
            err = str(e)
        if err:
            st.error(f"Couldn't shut down: {err}")
        else:
            st.success("Shutting down. Unplug once the green light stops blinking.")
