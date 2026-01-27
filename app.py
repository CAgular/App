import os
import uuid
import sqlite3
from datetime import datetime

import streamlit as st

# -----------------------------
# Config
# -----------------------------
APP_TITLE = "Household Memory"
DB_PATH = os.path.join("data", "memories.db")
PHOTOS_DIR = "photos"

# -----------------------------
# Helpers
# -----------------------------
def ensure_dirs():
    os.makedirs("data", exist_ok=True)
    os.makedirs(PHOTOS_DIR, exist_ok=True)

def get_conn():
    return sqlite3.connect(DB_PATH)

def init_db():
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                text TEXT NOT NULL,
                tags TEXT,
                photo_path TEXT NOT NULL
            )
        """)
        conn.commit()

def save_photo(uploaded_file) -> str:
    """Save uploaded photo to disk and return its relative path."""
    ext = os.path.splitext(uploaded_file.name)[1].lower()
    if ext not in [".jpg", ".jpeg", ".png", ".webp"]:
        ext = ".jpg"  # fallback
    filename = f"{uuid.uuid4().hex}{ext}"
    rel_path = os.path.join(PHOTOS_DIR, filename)

    with open(rel_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    return rel_path

def add_memory(text: str, tags: str, photo_path: str):
    mem_id = uuid.uuid4().hex
    created_at = datetime.now().isoformat(timespec="seconds")
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO memories (id, created_at, text, tags, photo_path) VALUES (?, ?, ?, ?, ?)",
            (mem_id, created_at, text.strip(), tags.strip(), photo_path),
        )
        conn.commit()

def fetch_recent(limit=20):
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT id, created_at, text, tags, photo_path FROM memories ORDER BY created_at DESC LIMIT ?",
            (limit,),
        )
        return cur.fetchall()

# -----------------------------
# App start
# -----------------------------
ensure_dirs()
init_db()

st.title("🏠 Household Memory")
st.caption("Remember once. Find later.")

st.divider()
st.subheader("➕ Add a memory")

with st.form("add_memory_form", clear_on_submit=True):
    uploaded = st.file_uploader("Photo (required)", type=["jpg", "jpeg", "png", "webp"])
    text = st.text_input("One-line memory (required)", placeholder="e.g. Hallway lamp → E14, max 40W")
    tags = st.text_input("Tags (optional, comma-separated)", placeholder="home, lighting")

    submitted = st.form_submit_button("Save memory")

    if submitted:
        if uploaded is None:
            st.error("Please upload a photo.")
        elif not text.strip():
            st.error("Please write one short line describing the memory.")
        else:
            photo_path = save_photo(uploaded)
            add_memory(text=text, tags=tags, photo_path=photo_path)
            st.success("Saved ✅")

st.divider()
st.subheader("🗂 Recent memories")

rows = fetch_recent(limit=30)
if not rows:
    st.info("No memories yet. Add your first one above 👆")
else:
    for _id, created_at, text, tags, photo_path in rows:
        with st.container(border=True):
            cols = st.columns([1, 2])
            with cols[0]:
                st.image(photo_path, use_container_width=True)
            with cols[1]:
                st.write(f"**{text}**")
                if tags:
                    st.caption(f"Tags: {tags}")
                st.caption(f"Added: {created_at}")