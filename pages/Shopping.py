import streamlit as st
from src.config import APP_TITLE

st.set_page_config(page_title=f"{APP_TITLE} • Shopping", page_icon="🛒", layout="centered")

st.title("🛒 Shopping")
st.caption("Placeholder-side. Her kan du lave indkøbsliste, favoritter, 'mangler', osv.")
st.info("Kommer snart 🙂")
