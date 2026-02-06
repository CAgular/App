import streamlit as st

# ============================================================
# Knudsen Home App – Forside
# ============================================================

APP_TITLE = "Knudsen Home App"

st.set_page_config(
    page_title=APP_TITLE,
    page_icon="🏠",
    layout="centered",
)

# ------------------------------------------------------------
# UI
# ------------------------------------------------------------

st.title("🏠 Knudsen Home App")
st.caption("Vælg en funktion nedenfor.")
st.divider()

col1, col2, col3 = st.columns(3)

with col1:
    if st.button("🏠 Memories", use_container_width=True):
        st.switch_page("pages/Memories.py")

with col2:
    if st.button("🧰 Maintenance", use_container_width=True):
        st.switch_page("pages/Maintenance.py")

with col3:
    if st.button("🛒 Shopping", use_container_width=True):
        st.switch_page("pages/Shopping.py")

st.divider()
st.caption("Tip: Du kan altid navigere via menuen i venstre side.")
