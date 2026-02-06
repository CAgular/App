import os
import uuid

from .config import PHOTOS_CACHE_DIR, ALLOWED_EXTS


def upload_uploadedfile_to_drive(drive, folder_id: str, uploaded_file):
    """
    Upload Streamlit UploadedFile til Drive via PyDrive2.
    Returnerer (drive_file_id, drive_file_name).
    """
    name = getattr(uploaded_file, "name", "") or ""
    ext = os.path.splitext(name)[1].lower()
    if ext not in ALLOWED_EXTS:
        ext = ".jpg"

    drive_name = f"{uuid.uuid4().hex}{ext}"

    tmp_path = os.path.join(PHOTOS_CACHE_DIR, f"tmp_{drive_name}")
    with open(tmp_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    gfile = drive.CreateFile({"title": drive_name, "parents": [{"id": folder_id}]})
    gfile.SetContentFile(tmp_path)
    gfile.Upload()

    try:
        os.remove(tmp_path)
    except OSError:
        pass

    return gfile["id"], drive_name


def download_drive_file_to_cache(drive, drive_file_id: str, cache_path: str) -> bool:
    try:
        os.makedirs(os.path.dirname(cache_path) or ".", exist_ok=True)
        gfile = drive.CreateFile({"id": drive_file_id})
        gfile.GetContentFile(cache_path)
        return True
    except Exception:
        return False


def delete_drive_file(drive, drive_file_id: str) -> bool:
    try:
        gfile = drive.CreateFile({"id": drive_file_id})
        gfile.Delete()
        return True
    except Exception:
        return False
