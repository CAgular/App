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

# Disse paths matcher Streamlits automatiske URL’er
st.link_button("🏠 Memories", "/Memories", use_container_width=True)
st.link_button("🧰 Maintenance", "/2_Maintenance", use_container_width=True)
st.link_button("🛒 Shopping", "/3_Shopping", use_container_width=True)

st.divider()
st.caption("Du kan også navigere via menuen i venstre side.")
