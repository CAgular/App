import os
import streamlit as st

from .config import DB_PATH, DB_DRIVE_NAME, PHOTOS_DIR, PHOTOS_CACHE_DIR
from .storage import init_db


def ensure_dirs() -> None:
    os.makedirs("data", exist_ok=True)
    os.makedirs(PHOTOS_DIR, exist_ok=True)
    os.makedirs(PHOTOS_CACHE_DIR, exist_ok=True)


def _looks_like_invalid_grant(err: Exception) -> bool:
    s = str(err).lower()
    return ("invalid_grant" in s) or ("token has been expired or revoked" in s)


@st.cache_resource(show_spinner=False)
def get_drive():
    """
    Cache Drive-connection pr session.
    Lazy-importer drive_sync så app ikke crasher ved import-problemer.
    """
    try:
        from drive_sync import connect_drive
        drive = connect_drive()
        return drive, None
    except Exception as e:
        if _looks_like_invalid_grant(e):
            try:
                get_drive.clear()
            except Exception:
                pass
        return None, e


def init_app_state():
    """
    Kaldes på hver side.
    Performance-fix:
      - Download DB fra Drive KUN én gang pr session (ikke ved hver rerun).
    """
    ensure_dirs()

    drive, drive_error = get_drive()

    # kun én gang pr session
    ss = st.session_state
    if "drive_db_checked" not in ss:
        ss["drive_db_checked"] = False

    downloaded_db = False
    if drive is not None and not ss["drive_db_checked"]:
        try:
            from drive_sync import download_if_exists, FOLDER_ID
            downloaded_db = download_if_exists(drive, FOLDER_ID, DB_DRIVE_NAME, DB_PATH)
        except Exception:
            downloaded_db = False
        finally:
            ss["drive_db_checked"] = True  # uanset succes
    else:
        downloaded_db = False

    init_db()

    return {
        "drive": drive,
        "drive_error": drive_error,
        "downloaded_db": downloaded_db,
    }
