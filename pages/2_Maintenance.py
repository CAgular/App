import streamlit as st
from src.config import APP_TITLE

st.set_page_config(page_title=f"{APP_TITLE} • Maintenance", page_icon="🧰", layout="centered")

st.title("🧰 Maintenance")
st.caption("Placeholder-side. Her kan du lave vedligeholdelseslog, service-intervaller, osv.")
st.info("Kommer snart 🙂")
