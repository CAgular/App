import os
import uuid
import sqlite3
from datetime import datetime

from .config import DB_PATH, PHOTOS_DIR, ALLOWED_EXTS


def get_conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def init_db() -> None:
    """
    Opret tabel + migrér gamle DB'er.
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

        cols = {row[1] for row in conn.execute("PRAGMA table_info(memories)").fetchall()}
        if "photo_drive_id" not in cols:
            conn.execute("ALTER TABLE memories ADD COLUMN photo_drive_id TEXT")
        if "photo_drive_name" not in cols:
            conn.execute("ALTER TABLE memories ADD COLUMN photo_drive_name TEXT")

        conn.commit()


def save_photo_locally(uploaded_file) -> str:
    """
    Gem foto lokalt og returner sti.
    Virker for både st.file_uploader og st.camera_input.
    """
    name = getattr(uploaded_file, "name", "") or ""
    ext = os.path.splitext(name)[1].lower()
    if ext not in ALLOWED_EXTS:
        ext = ".jpg"

    filename = f"{uuid.uuid4().hex}{ext}"
    rel_path = os.path.join(PHOTOS_DIR, filename)

    with open(rel_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    return rel_path


def add_memory(
    text: str,
    tags: str,
    photo_path: str,
    photo_drive_id=None,
    photo_drive_name=None,
) -> None:
    mem_id = uuid.uuid4().hex
    created_at = datetime.now().isoformat(timespec="seconds")

    text = (text or "").strip()
    tags = (tags or "").strip()

    with get_conn() as conn:
        conn.execute(
            """
            INSERT INTO memories (id, created_at, text, tags, photo_path, photo_drive_id, photo_drive_name)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (mem_id, created_at, text, tags, photo_path, photo_drive_id, photo_drive_name),
        )
        conn.commit()


def fetch_recent(limit: int = 30):
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


def delete_memory(mem_id: str) -> None:
    with get_conn() as conn:
        conn.execute("DELETE FROM memories WHERE id = ?", (mem_id,))
        conn.commit()
