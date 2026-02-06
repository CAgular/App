import streamlit as st

from src.config import APP_TITLE

st.set_page_config(page_title=APP_TITLE, page_icon="🏠", layout="centered")

st.title("🏠 Knudsen Home App")
st.caption("Vælg en funktion nedenfor.")

st.divider()

def go(page_path: str):
    # Streamlit har switch_page i nyere versioner.
    # Hvis ikke, viser vi i stedet side-links nederst.
    if hasattr(st, "switch_page"):
        st.switch_page(page_path)
    else:
        st.info("Din Streamlit-version mangler st.switch_page(). Brug side-menuen til venstre.")

c1, c2 = st.columns(2)
with c1:
    if st.button("🏠 Memories", use_container_width=True):
        go("pages/01_🏠_Memories.py")
with c2:
    if st.button("🧰 Maintenance", use_container_width=True):
        go("pages/02_🧰_Maintenance.py")

c3, c4 = st.columns(2)
with c3:
    if st.button("🛒 Shopping", use_container_width=True):
        go("pages/03_🛒_Shopping.py")
with c4:
    st.button("➕ Coming soon", use_container_width=True, disabled=True)

st.divider()
st.caption("Tip: Du kan altid navigere via side-menuen (venstre) i Streamlit.")
