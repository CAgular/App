import streamlit as st

APP_TITLE = "Knudsen Home App"

PAGES = [
    ("🏠 Memories", "/Memories"),
    ("🧰 Maintenance", "/Maintenance"),
    ("🛒 Shopping", "/Shopping"),
]

st.set_page_config(page_title=APP_TITLE, page_icon="🏠", layout="centered")

st.title("🏠 Knudsen Home App")
st.caption("Vælg en funktion nedenfor.")
st.divider()

for label, path in PAGES:
    st.link_button(label, path, use_container_width=True)

st.divider()
st.caption("Du kan også navigere via menuen i venstre side.")
