"""Streamlit UI: type a word, preview the sprite, send it to the display.

Never touches the LEDs; it only writes art/*.json and state.json.
Run: streamlit run app.py --server.address 0.0.0.0 --server.port 8501
"""
import json

import streamlit as st

import llm
import sprites

st.set_page_config(page_title="Unicorn", page_icon="🦄", layout="centered")
st.title("Unicorn HAT HD")


def read_state():
    try:
        return json.loads(sprites.STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"brightness": 0.5}


def run(word, force):
    with st.spinner(f"Drawing {word!r}..."):
        try:
            sprite, path, notes = llm.generate(word, force=force)
        except Exception as e:
            st.error(str(e))
            return
    st.session_state.path = str(path)
    st.session_state.notes = notes


with st.form("draw"):
    word = st.text_input("Word", placeholder="cat, rocket, pizza...")
    c1, c2 = st.columns(2)
    gen = c1.form_submit_button("Generate", type="primary", use_container_width=True)
    regen = c2.form_submit_button("Regenerate", use_container_width=True)
if (gen or regen) and word.strip():
    run(word.strip(), force=regen)

saved = sorted(sprites.ART_DIR.glob("*.json")) if sprites.ART_DIR.exists() else []
if saved:
    names = [p.stem for p in saved]
    current = st.session_state.get("path")
    idx = names.index(sprites.Path(current).stem) if current and sprites.Path(current).stem in names else 0
    pick = st.selectbox("Gallery", names, index=idx)
    if not current or sprites.Path(current).stem != pick:
        st.session_state.path = str(sprites.ART_DIR / f"{pick}.json")
        st.session_state.notes = []

path = st.session_state.get("path")
if path:
    sprite = sprites.load(path)
    n = len(sprite["frames"])
    st.image([sprites.to_image(sprite, i) for i in range(n)],
             caption=[f"frame {i}" for i in range(n)] if n > 1 else None)
    if st.session_state.get("notes"):
        st.caption(" · ".join(st.session_state.notes))

    state = read_state()
    brightness = st.slider("Brightness", 0.1, 1.0, float(state.get("brightness", 0.5)), 0.05)
    c1, c2 = st.columns(2)
    if c1.button("Show on display", type="primary", use_container_width=True):
        sprites.write_json(sprites.STATE_FILE, {"sprite": f"art/{sprites.Path(path).name}",
                                                "brightness": brightness})
        st.success("Sent")
    if c2.button("Display off", use_container_width=True):
        sprites.write_json(sprites.STATE_FILE, {"sprite": None, "brightness": brightness})
