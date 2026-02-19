# src/app_state.py
import os
import streamlit as st

from .config import DB_PATH, DB_DRIVE_NAME, PHOTOS_DIR, PHOTOS_CACHE_DIR
from .storage import init_db
from drive_sync import connect_drive, download_if_exists, FOLDER_ID


def ensure_dirs() -> None:
    os.makedirs("data", exist_ok=True)
    os.makedirs(PHOTOS_DIR, exist_ok=True)
    os.makedirs(PHOTOS_CACHE_DIR, exist_ok=True)


@st.cache_resource(show_spinner=False)
def get_drive():
    """
    Cache Drive-connection pr session.
    Hvis den fejler, returnerer vi None og en fejlbesked.
    Hvis invalid_grant -> clear cache, så næste rerun kan prøve igen efter du har opdateret secrets.
    """
    try:
        drive = connect_drive()
        return drive, None
    except Exception as e:
        s = str(e).lower()
        if "invalid_grant" in s or "token has been expired or revoked" in s:
            # Vigtigt: ellers kan en "død" error blive cached hele sessionen
            try:
                get_drive.clear()
            except Exception:
                pass
        return None, e


def init_app_state():
    """
    Kaldes på hver side. Sikker og enkel.
    - Sørger for mapper
    - Forsøger at hente DB fra Drive ved session-start (hvis drive virker)
    - Init DB schema/migrations
    """
    ensure_dirs()

    drive, drive_error = get_drive()

    downloaded_db = False
    if drive is not None:
        try:
            downloaded_db = download_if_exists(drive, FOLDER_ID, DB_DRIVE_NAME, DB_PATH)
        except Exception:
            downloaded_db = False

    init_db()

    return {
        "drive": drive,
        "drive_error": drive_error,
        "downloaded_db": downloaded_db,
    }
