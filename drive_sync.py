# drive_sync.py
import os
import json
import streamlit as st
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive

# Filplaceringer (lokalt + cloud)
SECRETS_DIR = "secrets"
OAUTH_CLIENT_PATH = os.path.join(SECRETS_DIR, "oauth_client.json")
DRIVE_CREDS_PATH = os.path.join(SECRETS_DIR, "drive_creds.json")
SETTINGS_PATH = "settings.yaml"

# Fallback hvis folder_id ikke ligger i Streamlit secrets
FOLDER_ID = "13w00cOsmmc2EBPej4dBwBVw2SYWnK4ym"


def _write_text_file(path: str, text: str):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write(text)


def ensure_cloud_secrets_files():
    """
    Streamlit Cloud har ikke dine lokale filer.
    Hvis secrets er sat i Streamlit Cloud UI, skriver vi dem til disk som JSON-filer.
    """
    os.makedirs(SECRETS_DIR, exist_ok=True)

    # Læs JSON som tekst fra Streamlit secrets (TOML)
    oauth_json_text = st.secrets.get("oauth_client_json", None)
    creds_json_text = st.secrets.get("drive_creds_json", None)

    if oauth_json_text:
        json.loads(oauth_json_text)  # validate JSON
        _write_text_file(OAUTH_CLIENT_PATH, oauth_json_text)

    if creds_json_text:
        json.loads(creds_json_text)  # validate JSON
        _write_text_file(DRIVE_CREDS_PATH, creds_json_text)


def connect_drive():
    """
    Forbinder til Google Drive via pydrive2 + settings.yaml.
    Kræver oauth_client.json + drive_creds.json på disk.
    På Cloud bliver de skrevet fra st.secrets.

    Robust mod invalid_grant:
      - sletter secrets/drive_creds.json
      - beder om at du genskaber den lokalt og opdaterer drive_creds_json i Streamlit Secrets
    """
    global FOLDER_ID
    FOLDER_ID = st.secrets.get("folder_id", FOLDER_ID)

    ensure_cloud_secrets_files()

    if not os.path.exists(OAUTH_CLIENT_PATH):
        raise RuntimeError("Missing oauth client secrets. Add oauth_client_json in Streamlit Secrets.")
    if not os.path.exists(DRIVE_CREDS_PATH):
        raise RuntimeError("Missing drive credentials. Add drive_creds_json in Streamlit Secrets.")

    gauth = GoogleAuth(settings_file=SETTINGS_PATH)
    gauth.LoadCredentialsFile(DRIVE_CREDS_PATH)

    if gauth.credentials is None:
        raise RuntimeError("Drive credentials are empty. Recreate drive_creds.json locally with OAuth first.")

    try:
        if gauth.access_token_expired:
            gauth.Refresh()
        else:
            gauth.Authorize()

        gauth.SaveCredentialsFile(DRIVE_CREDS_PATH)
        return GoogleDrive(gauth)

    except Exception as e:
        msg = str(e).lower()
        if "invalid_grant" in msg or "token has been expired or revoked" in msg or "bad request" in msg:
            # Slet døde creds så vi ikke bliver ved at refresh'e en invalid token
            try:
                if os.path.exists(DRIVE_CREDS_PATH):
                    os.remove(DRIVE_CREDS_PATH)
            except Exception:
                pass

            raise RuntimeError(
                "Access token refresh failed: invalid_grant. "
                "Deleted secrets/drive_creds.json. "
                "Recreate drive_creds.json locally and update drive_creds_json in Streamlit Secrets."
            ) from e

        raise


def find_file_in_folder(drive, folder_id: str, filename: str):
    q = f"'{folder_id}' in parents and trashed=false and title='{filename}'"
    files = drive.ListFile({"q": q}).GetList()
    return files[0] if files else None


def download_if_exists(drive, folder_id: str, drive_name: str, local_path: str) -> bool:
    f = find_file_in_folder(drive, folder_id, drive_name)
    if not f:
        return False
    os.makedirs(os.path.dirname(local_path) or ".", exist_ok=True)
    f.GetContentFile(local_path)
    return True


def upload_or_update(drive, folder_id: str, local_path: str, drive_name: str):
    existing = find_file_in_folder(drive, folder_id, drive_name)
    if existing:
        existing.SetContentFile(local_path)
        existing.Upload()
        return existing["id"], "updated"

    f = drive.CreateFile({"title": drive_name, "parents": [{"id": folder_id}]})
    f.SetContentFile(local_path)
    f.Upload()
    return f["id"], "uploaded"
