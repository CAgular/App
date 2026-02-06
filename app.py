# ============================================================
# Household Memory - app.py
# ------------------------------------------------------------
# En lille “memory”-app:
# - Gem en kort tekst + tags + et foto (kamera eller upload)
# - Gemmer lokalt i SQLite + lokale fotos
# - Sync'er DB og fotos til Google Drive, hvis Drive kan forbindes
# - Viser seneste memories og gør det muligt at slette igen
# ============================================================

import os
import uuid
import sqlite3
from datetime import datetime

import streamlit as st

from drive_sync import connect_drive, download_if_exists, upload_or_update, FOLDER_ID


# ============================================================
# 1) Config
# ============================================================

APP_TITLE = "Knudsen HomeApp"

DB_PATH = os.path.join("data", "memories.db")
DB_DRIVE_NAME = "memories.db"

PHOTOS_DIR = "photos"              # lokale fotos (typisk hjemme/PC)
PHOTOS_CACHE_DIR = "photos_cache"  # cache for Drive-downloadede fotos (typisk cloud/mobil)

ALLOWED_EXTS = [".jpg", ".jpeg", ".png", ".webp"]

st.set_page_config(page_title=APP_TITLE, page_icon="🏠", layout="centered")


# ============================================================
# 2) Fil/DB helpers (lokal lagring)
# ============================================================

def ensure_dirs() -> None:
    """Sikrer at nødvendige mapper findes."""
    os.makedirs("data", exist_ok=True)
    os.makedirs(PHOTOS_DIR, exist_ok=True)
    os.makedirs(PHOTOS_CACHE_DIR, exist_ok=True)


def get_conn():
    """Åbner SQLite connection. check_same_thread=False er praktisk med Streamlit reruns."""
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def init_db() -> None:
    """
    Opretter tabellen hvis den ikke findes.
    Indeholder også migration, hvis du har en ældre DB uden Drive-kolonner.
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

        # Migration for eksisterende DB'er:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(memories)").fetchall()}
        if "photo_drive_id" not in cols:
            conn.execute("ALTER TABLE memories ADD COLUMN photo_drive_id TEXT")
        if "photo_drive_name" not in cols:
            conn.execute("ALTER TABLE memories ADD COLUMN photo_drive_name TEXT")

        conn.commit()


def save_photo_locally(uploaded_file) -> str:
    """
    Gemmer et uploaded foto til disk og returnerer relativ sti.
    Virker både for st.file_uploader og st.camera_input.
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


def add_memory(text: str, tags: str, photo_path: str, photo_drive_id=None, photo_drive_name=None) -> None:
    """Indsætter en memory i databasen."""
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


def fetch_recent(limit: int = 30):
    """Henter de nyeste memories."""
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
    """Sletter en memory fra databasen."""
    with get_conn() as conn:
        conn.execute("DELETE FROM memories WHERE id = ?", (mem_id,))
        conn.commit()


# ============================================================
# 3) Google Drive helpers (fotos)
# ============================================================

def upload_uploadedfile_to_drive(drive, folder_id: str, uploaded_file):
    """
    Upload en Streamlit UploadedFile til Drive (PyDrive2).
    Returnerer (drive_file_id, drive_file_name).
    """
    name = getattr(uploaded_file, "name", "") or ""
    ext = os.path.splitext(name)[1].lower()
    if ext not in ALLOWED_EXTS:
        ext = ".jpg"

    drive_name = f"{uuid.uuid4().hex}{ext}"

    # PyDrive2 forventer en filepath, så vi skriver en midlertidig fil
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
    """Downloader Drive fil til cache_path. Returnerer True hvis ok."""
    try:
        os.makedirs(os.path.dirname(cache_path) or ".", exist_ok=True)
        gfile = drive.CreateFile({"id": drive_file_id})
        gfile.GetContentFile(cache_path)
        return True
    except Exception:
        return False


def delete_drive_file(drive, drive_file_id: str) -> bool:
    """Sletter en Drive-fil (hvis drive er connected)."""
    try:
        gfile = drive.CreateFile({"id": drive_file_id})
        gfile.Delete()
        return True
    except Exception:
        return False


def cleanup_photos(photo_path: str | None, photo_drive_id: str | None, photo_drive_name: str | None, drive) -> None:
    """
    Sletter lokale/cached fotos + Drive foto (hvis muligt).
    Bemærk: Drive-slet kræver drive forbindelse.
    """
    # 1) lokal fil
    if photo_path and os.path.exists(photo_path):
        try:
            os.remove(photo_path)
        except OSError:
            pass

    # 2) cached drive foto
    if photo_drive_id:
        ext = os.path.splitext(photo_drive_name or "")[1].lower()
        if ext not in ALLOWED_EXTS:
            ext = ".jpg"
        cache_path = os.path.join(PHOTOS_CACHE_DIR, f"{photo_drive_id}{ext}")
        if os.path.exists(cache_path):
            try:
                os.remove(cache_path)
            except OSError:
                pass

    # 3) drive fil
    if drive is not None and photo_drive_id:
        delete_drive_file(drive, photo_drive_id)


# ============================================================
# 4) App start: mapper + Drive DB-sync + DB init
# ============================================================

ensure_dirs()

drive = None
downloaded_db = False
drive_error = None

# Forsøg at forbinde Drive og hente DB først (så du ser “seneste” i cloud)
try:
    drive = connect_drive()
    downloaded_db = download_if_exists(drive, FOLDER_ID, DB_DRIVE_NAME, DB_PATH)
except Exception as e:
    drive = None
    downloaded_db = False
    drive_error = e

init_db()

st.title("🏠 Knudsen HomeApp")
st.caption("Husk én gang - Husk altid.")

with st.expander("Drive sync status", expanded=False):
    if drive is None:
        st.warning(f"Drive sync disabled (could not connect): {drive_error}")
    else:
        st.success("Drive connected ✅")
        if downloaded_db:
            st.info("Downloaded latest database from Drive ✅")
        else:
            st.info("No database found in Drive (or first run). Using local DB.")


# ============================================================
# 5) Add memory UI (kamera eller upload)
# ============================================================

st.divider()
st.subheader("➕ Add a memory")

# saving-flag: bruges til at disable knappen under gemning
if "saving" not in st.session_state:
    st.session_state["saving"] = False

# (valgfrit) en super-enkel anti-dobbelt-submit i 2 sekunder
if "last_save_token" not in st.session_state:
    st.session_state["last_save_token"] = None
if "last_save_time" not in st.session_state:
    st.session_state["last_save_time"] = 0.0

with st.form("Tilføj et punkt", clear_on_submit=True):

    source = st.radio(
        "Vælg hvordan du vil tilføje foto",
        ["📷 Kamera", "📁 Browse / upload"],
        horizontal=True,
    )

    uploaded = None
    if source == "📷 Kamera":
        uploaded = st.camera_input("Tag et billede")
    else:
        uploaded = st.file_uploader("Vælg et billede", type=["jpg", "jpeg", "png", "webp"])

    text = st.text_input(
        "Beskrivelse",
        placeholder="F.eks. Entrelampe → E14, max 40W",
    )

    tags = st.text_input(
        "Tags kommasepareret)",
        placeholder=("F.eks. Lys, Entre")
    )

    submitted = st.form_submit_button("Gem", disabled=st.session_state["saving"])

    if submitted:
        st.session_state["saving"] = True
        try:
            # Validation
            if uploaded is None:
                st.error("Please add a photo (camera or upload).")
                st.stop()
            if not text.strip():
                st.error("Please write one short line describing the memory.")
                st.stop()

            # Anti-dobbelt-submit (meget simpel):
            # Hvis samme (text+tags) gemmes igen indenfor 2 sek, ignorer
            now_ts = datetime.now().timestamp()
            token = f"{text.strip()}|{tags.strip()}"
            if st.session_state["last_save_token"] == token and (now_ts - st.session_state["last_save_time"]) < 2:
                st.warning("Ignored duplicate submit (too fast).")
                st.stop()
            st.session_state["last_save_token"] = token
            st.session_state["last_save_time"] = now_ts

            # 1) Gem foto lokalt
            photo_path = save_photo_locally(uploaded)

            # 2) Upload foto til Drive (hvis muligt)
            photo_drive_id = None
            photo_drive_name = None
            if drive is not None:
                try:
                    photo_drive_id, photo_drive_name = upload_uploadedfile_to_drive(drive, FOLDER_ID, uploaded)
                except Exception as e:
                    st.warning(f"Saved locally, but failed to upload photo to Drive: {e}")

            # 3) Gem memory i DB
            add_memory(
                text=text,
                tags=tags,
                photo_path=photo_path,
                photo_drive_id=photo_drive_id,
                photo_drive_name=photo_drive_name,
            )

            # 4) Sync DB til Drive (hvis muligt)
            if drive is not None:
                try:
                    upload_or_update(drive, FOLDER_ID, DB_PATH, DB_DRIVE_NAME)
                except Exception as e:
                    st.warning(f"Saved locally, but failed to sync DB to Drive: {e}")

            st.success("Saved ✅")

        finally:
            # VIGTIGT: altid unlock knappen igen
            st.session_state["saving"] = False


# ============================================================
# 6) Vis nylige memories + slet
# ============================================================

st.divider()
st.subheader("🗂 Recent memories")

rows = fetch_recent(limit=30)
if not rows:
    st.info("No memories yet. Add your first one above 👆")
else:
    for _id, created_at, text, tags, photo_path, photo_drive_id, photo_drive_name in rows:
        with st.container(border=True):

            # --- Toplinje: dato + slet-knap ---
            top = st.columns([3, 1])
            with top[0]:
                st.caption(f"Added: {created_at}")

            with top[1]:
                confirm_key = f"confirm_delete_{_id}"
                if confirm_key not in st.session_state:
                    st.session_state[confirm_key] = False

                if not st.session_state[confirm_key]:
                    if st.button("🗑️ Slet", key=f"del_{_id}"):
                        st.session_state[confirm_key] = True
                        st.rerun()
                else:
                    st.warning("Vil du slette denne memory?")
                    c1, c2 = st.columns(2)
                    with c1:
                        if st.button("Ja, slet", key=f"del_yes_{_id}"):
                            # 1) slet fotos (lokal + cache + evt Drive)
                            cleanup_photos(photo_path, photo_drive_id, photo_drive_name, drive)

                            # 2) slet DB row
                            delete_memory(_id)

                            # 3) sync DB til Drive
                            if drive is not None:
                                try:
                                    upload_or_update(drive, FOLDER_ID, DB_PATH, DB_DRIVE_NAME)
                                except Exception as e:
                                    st.warning(f"Slettet lokalt, men kunne ikke sync DB til Drive: {e}")

                            st.session_state[confirm_key] = False
                            st.success("Slettet ✅")
                            st.rerun()

                    with c2:
                        if st.button("Annuller", key=f"del_no_{_id}"):
                            st.session_state[confirm_key] = False
                            st.rerun()

            # --- Indhold: billede + tekst/tags ---
            cols = st.columns([1, 2])

            with cols[0]:
                # 1) Prefer local photo if available
                if photo_path and os.path.exists(photo_path):
                    st.image(photo_path, use_container_width=True)

                # 2) Otherwise try Drive photo (download to cache)
                elif drive is not None and photo_drive_id:
                    ext = os.path.splitext(photo_drive_name or "")[1].lower()
                    if ext not in ALLOWED_EXTS:
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

