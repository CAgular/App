import os
from pydrive2.auth import GoogleAuth
from pydrive2.drive import GoogleDrive

SETTINGS_FILE = "settings.yaml"
CREDS_FILE = "secrets/drive_creds.json"

# Din mappe i Drive
FOLDER_ID = "13w00cOsmmc2EBPej4dBwBVw2SYWnK4ym"

def connect_drive():
    os.makedirs("secrets", exist_ok=True)
    gauth = GoogleAuth(settings_file=SETTINGS_FILE)
    gauth.LoadCredentialsFile(CREDS_FILE)

    if gauth.credentials is None:
        gauth.LocalWebserverAuth()
    elif gauth.access_token_expired:
        gauth.Refresh()
    else:
        gauth.Authorize()

    gauth.SaveCredentialsFile(CREDS_FILE)
    return GoogleDrive(gauth)

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
