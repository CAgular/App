import os
import uuid
import sqlite3
from datetime import datetime

import streamlit as st

from drive_sync import connect_drive, download_if_exists, upload_or_update, FOLDER_ID

# -----------------------------
# Config
# -----------------------------
APP_TITLE = "Household Memory"

DB_PATH = os.path.join("data", "memories.db")
DB_DRIVE_NAME = "memories.db"

PHOTOS_DIR = "photos"              # local photos (works at home)
PHOTOS_CACHE_DIR = "photos_cache"  # cache for downloaded Drive photos (works on Cloud/iPhone)

st.set_page_config(page_title=APP_TITLE, page_icon="🏠", layout="centered")


# -----------------------------
# Helpers (local storage)
# -----------------------------
def ensure_dirs():
    os.makedirs("data", exist_ok=True)
    os.makedirs(PHOTOS_DIR, exist_ok=True)
    os.makedirs(PHOTOS_CACHE_DIR, exist_ok=True)


def get_conn():
    # check_same_thread=False is helpful with Streamlit reruns
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def init_db():
    """
    Create table if not exists + migrate older DBs to include Drive photo fields.
    """
    with get_conn() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS memories (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                text TEXT NOT NULL,
                tags TEXT,
                photo_path TEXT NOT NULL,
                photo_drive_id TEXT,
                photo_drive_name TEXT
            )
            """
        )

        # Migration for existing DBs that don't have new columns yet
        cols = {row[1] for row in conn.execute("PRAGMA table_info(memories)").fetchall()}
        if "photo_drive_id" not in cols:
            conn.execute("ALTER TABLE memories ADD COLUMN photo_drive_id TEXT")
        if "photo_drive_name" not in cols:
            conn.execute("ALTER TABLE memories ADD COLUMN photo_drive_name TEXT")

        conn.commit()


def save_photo_locally(uploaded_file) -> str:
    """Save uploaded photo to disk and return its relative path."""
    ext = os.path.splitext(uploaded_file.name)[1].lower()
    if ext not in [".jpg", ".jpeg", ".png", ".webp"]:
        ext = ".jpg"

    filename = f"{uuid.uuid4().hex}{ext}"
    rel_path = os.path.join(PHOTOS_DIR, filename)

    with open(rel_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    return rel_path


def add_memory(text: str, tags: str, photo_path: str, photo_drive_id=None, photo_drive_name=None):
    mem_id = uuid.uuid4().hex
    created_at = datetime.now().isoformat(timespec="seconds")

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO memories (id, created_at, text, tags, photo_path, photo_drive_id, photo_drive_name)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (mem_id, created_at, text.strip(), tags.strip(), photo_path, photo_drive_id, photo_drive_name),
        )
        conn.commit()


def fetch_recent(limit=30):
    with get_conn() as conn:
        cur = conn.execute(
            """
            SELECT id, created_at, text, tags, photo_path, photo_drive_id, photo_drive_name
            FROM memories
            ORDER BY created_at DESC
            LIMIT ?
            """,
            (limit,),
        )
        return cur.fetchall()


# -----------------------------
# Helpers (Google Drive photos)
# -----------------------------
def upload_uploadedfile_to_drive(drive, folder_id: str, uploaded_file):
    """
    Upload a Streamlit UploadedFile to Google Drive.
    Returns (drive_file_id, drive_name).
    """
    ext = os.path.splitext(uploaded_file.name)[1].lower()
    if ext not in [".jpg", ".jpeg", ".png", ".webp"]:
        ext = ".jpg"

    drive_name = f"{uuid.uuid4().hex}{ext}"

    # Write temporary file (pydrive2 expects a filepath)
    tmp_path = os.path.join(PHOTOS_CACHE_DIR, f"tmp_{drive_name}")
    with open(tmp_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    gfile = drive.CreateFile({"title": drive_name, "parents": [{"id": folder_id}]})
    gfile.SetContentFile(tmp_path)
    gfile.Upload()

    # Cleanup temp file
    try:
        os.remove(tmp_path)
    except OSError:
        pass

    return gfile["id"], drive_name


def download_drive_file_to_cache(drive, drive_file_id: str, cache_path: str) -> bool:
    """
    Download a Drive file (by file id) to cache_path.
    Returns True if OK.
    """
    try:
        os.makedirs(os.path.dirname(cache_path) or ".", exist_ok=True)
        gfile = drive.CreateFile({"id": drive_file_id})
        gfile.GetContentFile(cache_path)
        return True
    except Exception:
        return False


# -----------------------------
# App start
# -----------------------------
ensure_dirs()

# --- Google Drive sync: download DB if it exists ---
drive = None
downloaded_db = False
drive_error = None

try:
    drive = connect_drive()
    downloaded_db = download_if_exists(drive, FOLDER_ID, DB_DRIVE_NAME, DB_PATH)
except Exception as e:
    drive = None
    downloaded_db = False
    drive_error = e

init_db()

st.title("🏠 Household Memory")
st.caption("Remember once. Find later.")

with st.expander("Drive sync status", expanded=False):
    if drive is None:
        st.warning(f"Drive sync disabled (could not connect): {drive_error}")
    else:
        st.success("Drive connected ✅")
        if downloaded_db:
            st.info("Downloaded latest database from Drive ✅")
        else:
            st.info("No database found in Drive (or first run). Using local DB.")


st.divider()
st.subheader("➕ Add a memory")

with st.form("add_memory_form", clear_on_submit=True):
    uploaded = st.file_uploader("Photo (required)", type=["jpg", "jpeg", "png", "webp"])
    text = st.text_input(
        "One-line memory (required)",
        placeholder="e.g. Hallway lamp → E14, max 40W",
    )
    tags = st.text_input(
        "Tags (optional, comma-separated)",
        placeholder="home, lighting",
    )

    submitted = st.form_submit_button("Save memory")

    if submitted:
        if uploaded is None:
            st.error("Please upload a photo.")
        elif not text.strip():
            st.error("Please write one short line describing the memory.")
        else:
            # Save locally (home mode)
            photo_path = save_photo_locally(uploaded)

            # Upload photo to Drive (cloud mode)
            photo_drive_id = None
            photo_drive_name = None
            if drive is not None:
                try:
                    photo_drive_id, photo_drive_name = upload_uploadedfile_to_drive(drive, FOLDER_ID, uploaded)
                except Exception as e:
                    st.warning(f"Saved locally, but failed to upload photo to Drive: {e}")

            # Save row in DB
            add_memory(
                text=text,
                tags=tags,
                photo_path=photo_path,
                photo_drive_id=photo_drive_id,
                photo_drive_name=photo_drive_name,
            )

            # Upload DB after change
            if drive is not None:
                try:
                    upload_or_update(drive, FOLDER_ID, DB_PATH, DB_DRIVE_NAME)
                except Exception as e:
                    st.warning(f"Saved locally, but failed to sync DB to Drive: {e}")

            st.success("Saved ✅")


st.divider()
st.subheader("🗂 Recent memories")

rows = fetch_recent(limit=30)
if not rows:
    st.info("No memories yet. Add your first one above 👆")
else:
    for _id, created_at, text, tags, photo_path, photo_drive_id, photo_drive_name in rows:
        with st.container(border=True):
            cols = st.columns([1, 2])

            with cols[0]:
                # 1) Prefer local photo if available
                if photo_path and os.path.exists(photo_path):
                    st.image(photo_path, use_container_width=True)

                # 2) Otherwise try Drive photo (download to cache)
                elif drive is not None and photo_drive_id:
                    ext = os.path.splitext(photo_drive_name or "")[1].lower()
                    if ext not in [".jpg", ".jpeg", ".png", ".webp"]:
                        ext = ".jpg"

                    cache_path = os.path.join(PHOTOS_CACHE_DIR, f"{photo_drive_id}{ext}")

                    if not os.path.exists(cache_path):
                        ok = download_drive_file_to_cache(drive, photo_drive_id, cache_path)
                        if not ok:
                            st.warning("Could not download photo from Drive.")

                    if os.path.exists(cache_path):
                        st.image(cache_path, use_container_width=True)
                    else:
                        st.warning("Photo missing.")

                else:
                    st.warning("Photo not found.")

            with cols[1]:
                st.write(f"**{text}**")
                if tags:
                    st.caption(f"Tags: {tags}")
                st.caption(f"Added: {created_at}")
