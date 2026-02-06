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

# "Knapper" der virker i alle Streamlit Cloud setups
st.page_link("pages/Memories.py", label="🏠 Memories", use_container_width=True)
st.page_link("pages/Maintenance.py", label="🧰 Maintenance", use_container_width=True)
st.page_link("pages/Shopping.py", label="🛒 Shopping", use_container_width=True)

st.divider()
st.caption("Tip: Du kan også bruge menuen i venstre side.")
