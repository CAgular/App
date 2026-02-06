import os
import streamlit as st

from src.app_state import init_app_state
from src.config import APP_TITLE, DB_PATH, DB_DRIVE_NAME, PHOTOS_CACHE_DIR, ALLOWED_EXTS
from src.storage import save_photo_locally, add_memory, fetch_recent, delete_memory
from src.drive_media import upload_uploadedfile_to_drive, download_drive_file_to_cache, delete_drive_file
from drive_sync import upload_or_update, FOLDER_ID

st.set_page_config(page_title=f"{APP_TITLE} • Memories", page_icon="🏠", layout="centered")

# -----------------------------
# Init (Drive + DB)
# -----------------------------
state = init_app_state()
drive = state["drive"]
drive_error = state["drive_error"]
downloaded_db = state["downloaded_db"]

st.title("🏠 Memories")
st.caption("Remember once. Find later.")

with st.expander("Drive sync status", expanded=False):
    if drive is None:
        st.warning(f"Drive sync disabled (could not connect): {drive_error}")
    else:
        st.success("Drive connected ✅")
        st.info("Downloaded latest database from Drive ✅" if downloaded_db else "No database found in Drive (or first run). Using local DB.")


# -----------------------------
# Add memory
# -----------------------------
st.divider()
st.subheader("➕ Add a memory")

if "saving" not in st.session_state:
    st.session_state["saving"] = False

with st.form("add_memory_form", clear_on_submit=True):

    source = st.radio(
        "Vælg hvordan du vil tilføje foto",
        ["📷 Kamera", "📁 Browse / upload"],
        horizontal=True,
    )

    uploaded = st.camera_input("Tag et billede") if source == "📷 Kamera" else st.file_uploader(
        "Vælg et billede", type=["jpg", "jpeg", "png", "webp"]
    )

    text = st.text_input("One-line memory (required)", placeholder="e.g. Hallway lamp → E14, max 40W")
    tags = st.text_input("Tags (optional, comma-separated)", placeholder="home, lighting")

    submitted = st.form_submit_button("Save memory", disabled=st.session_state["saving"])

    if submitted:
        st.session_state["saving"] = True
        try:
            if uploaded is None:
                st.error("Please add a photo (camera or upload).")
                st.stop()
            if not text.strip():
                st.error("Please write one short line describing the memory.")
                st.stop()

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

            # 3) Gem DB-row
            add_memory(text=text, tags=tags, photo_path=photo_path, photo_drive_id=photo_drive_id, photo_drive_name=photo_drive_name)

            # 4) Sync DB til Drive
            if drive is not None:
                try:
                    upload_or_update(drive, FOLDER_ID, DB_PATH, DB_DRIVE_NAME)
                except Exception as e:
                    st.warning(f"Saved locally, but failed to sync DB to Drive: {e}")

            st.success("Saved ✅")

        finally:
            st.session_state["saving"] = False


# -----------------------------
# Helpers: cleanup photos
# -----------------------------
def cleanup_photos(photo_path, photo_drive_id, photo_drive_name):
    # Lokal foto
    if photo_path and os.path.exists(photo_path):
        try:
            os.remove(photo_path)
        except OSError:
            pass

    # Cache foto
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

    # Drive foto
    if drive is not None and photo_drive_id:
        delete_drive_file(drive, photo_drive_id)


# -----------------------------
# Recent memories + delete
# -----------------------------
st.divider()
st.subheader("🗂 Recent memories")

rows = fetch_recent(limit=30)
if not rows:
    st.info("No memories yet. Add your first one above 👆")
else:
    for _id, created_at, text, tags, photo_path, photo_drive_id, photo_drive_name in rows:
        with st.container(border=True):

            # Top line: timestamp + delete
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
                            cleanup_photos(photo_path, photo_drive_id, photo_drive_name)
                            delete_memory(_id)

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

            # Content: image + text/tags
            cols = st.columns([1, 2])
            with cols[0]:
                if photo_path and os.path.exists(photo_path):
                    st.image(photo_path, use_container_width=True)
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
