def connect_drive():
    """
    Forbinder til Google Drive via pydrive2 + settings.yaml.
    Kræver oauth_client.json + drive_creds.json på disk.
    På Cloud bliver de skrevet fra st.secrets.
    """
    global FOLDER_ID
    FOLDER_ID = st.secrets.get("folder_id", FOLDER_ID)

    ensure_cloud_secrets_files()

    # Hvis filerne stadig ikke findes, kan vi ikke forbinde
    if not os.path.exists(OAUTH_CLIENT_PATH):
        raise RuntimeError("Missing oauth client secrets. Add oauth_client_json in Streamlit Secrets.")
    if not os.path.exists(DRIVE_CREDS_PATH):
        raise RuntimeError("Missing drive credentials. Add drive_creds_json in Streamlit Secrets.")

    gauth = GoogleAuth(settings_file=SETTINGS_PATH)
    gauth.LoadCredentialsFile(DRIVE_CREDS_PATH)

    # På cloud kan vi ikke lave interaktiv login. Vi forventer creds findes.
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
        # ✅ A: Selv-helende invalid_grant
        msg = str(e).lower()
        if "invalid_grant" in msg or "token has been expired or revoked" in msg:
            # Slet den lokale creds-fil, så vi ikke sidder fast med en død refresh_token
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

        # andre fejl bobler op
        raise
