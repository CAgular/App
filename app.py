import streamlit as st

APP_TITLE = "Knudsen Home App"

st.set_page_config(
    page_title=APP_TITLE,
    page_icon="🏠",
    layout="centered",
)

st.title("🏠 Knudsen Home App")
st.caption("Vælg en funktion nedenfor.")
st.divider()

st.link_button("🏠 Memories", "/pages/1_Memories", use_container_width=True)
st.link_button("🧰 Maintenance", "/Maintenance", use_container_width=True)
st.link_button("🛒 Shopping", "/Shopping", use_container_width=True)

st.divider()
st.caption("Tip: Du kan også bruge menuen i venstre side.")
