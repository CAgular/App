# pages/Shopping.py
# -*- coding: utf-8 -*-
import streamlit as st

from src.app_state import init_app_state
from src.config import APP_TITLE, DB_PATH, DB_DRIVE_NAME
from src.storage_shopping import (
    init_shopping_tables,
    fetch_shopping,
    fetch_pantry,
    add_shopping,
    delete_shopping,
    pop_shopping,
    pantry_add_or_merge,
    pantry_set_location,
    pantry_used_add_back,
)

import drive_sync  # robust: så crasher vi ikke på "from drive_sync import ..."

st.set_page_config(page_title=f"{APP_TITLE} • Shopping", page_icon="🛒", layout="centered")
st.link_button("⬅️ Tilbage til forside", "/")

# -----------------------------
# Init (Drive + DB)
# -----------------------------
state = init_app_state()
drive = state["drive"]
drive_error = state["drive_error"]
downloaded_db = state["downloaded_db"]

init_shopping_tables()

st.title("🛒 Shopping")

with st.expander("Drive sync status", expanded=False):
    if drive is None:
        st.warning(f"Drive sync disabled (could not connect): {drive_error}")
    else:
        st.success("Drive connected ✅")
        st.info(
            "Downloaded latest database from Drive ✅"
            if downloaded_db
            else "No database found in Drive (or first run). Using local DB."
        )


def sync_db():
    if drive is None:
        return
    try:
        drive_sync.upload_or_update(drive, drive_sync.FOLDER_ID, DB_PATH, DB_DRIVE_NAME)
    except Exception as e:
        st.warning(f"Saved locally, but failed to sync DB to Drive: {e}")


def _parse_qty(s) -> float:
    s = (s or "").strip()
    if not s:
        return 1.0
    s = s.replace(",", ".")
    try:
        q = float(s)
    except Exception:
        return 1.0
    return 1.0 if q <= 0 else q


def _fmt_qty(q: float) -> str:
    q = float(q)
    return str(int(q)) if q.is_integer() else str(q)


ss = st.session_state
ss.setdefault("new_item_text", "")
ss.setdefault("new_item_qty_text", "1")
ss.setdefault("new_item_cat", "Ukategoriseret")

ss.setdefault("shopping_categories", [
    "Frugt & grønt",
    "Kød & fisk",
    "Mejeri",
    "Brød",
    "Kolonial",
    "Frost",
    "Drikkevarer",
    "Diverse",
    "Ukategoriseret",
])

ss.setdefault("pantry_locations", [
    "Køleskab",
    "Fryser",
    "Bryggers",
    "Skab",
    "Badeværelse",
    "Kælder",
    "Garage",
    "Ukategoriseret",
])

ss.setdefault("pantry_prompt_uid", None)
ss.setdefault("pantry_prompt_qty_text", "1")

tab_shop, tab_pantry = st.tabs(["Indkøbsliste", "Hjemme"])

# -----------------------------
# TAB: Indkøbsliste
# -----------------------------
with tab_shop:
    with st.form("add_item_form", border=False):
        with st.container(horizontal=True, vertical_alignment="bottom"):
            st.text_input("Vare", label_visibility="collapsed", placeholder="Tilføj vare…", key="new_item_text")
            st.text_input("Antal", label_visibility="collapsed", placeholder="Antal", key="new_item_qty_text")
            st.selectbox("Kategori", ss["shopping_categories"], key="new_item_cat", label_visibility="collapsed")
            submitted = st.form_submit_button("Tilføj", icon=":material/add:")

        if submitted:
            text = (ss["new_item_text"] or "").strip()
            if text:
                qty = _parse_qty(ss["new_item_qty_text"])
                cat = (ss["new_item_cat"] or "Ukategoriseret").strip() or "Ukategoriseret"
                add_shopping(text=text, qty=qty, category=cat)
                ss["new_item_text"] = ""
                ss["new_item_qty_text"] = "1"
                sync_db()
                st.rerun()

    rows = fetch_shopping()
    if not rows:
        st.info("Listen er tom.")
    else:
        def cat_key(c: str):
            return ("zzzz" if c == "Ukategoriseret" else c.lower())

        cats = sorted({(r[3] or "Ukategoriseret") for r in rows}, key=cat_key)

        with st.container(gap=None, border=True):
            for cat in cats:
                group = [r for r in rows if (r[3] or "Ukategoriseret") == cat]
                for uid, text, qty, _cat in group:
                    with st.container(horizontal=True, vertical_alignment="center"):
                        st.markdown(f"{_fmt_qty(qty)} × {text}")

                        if st.button("Købt", key=f"shop_b_{uid}", type="secondary"):
                            popped = pop_shopping(uid)
                            if popped:
                                t, q, _c = popped
                                pantry_add_or_merge(t, q)
                                sync_db()
                            st.rerun()

                        if st.button(":material/delete:", key=f"shop_r_{uid}", type="tertiary"):
                            delete_shopping(uid)
                            sync_db()
                            st.rerun()

# -----------------------------
# TAB: Hjemme
# -----------------------------
with tab_pantry:
    prompt_uid = ss.get("pantry_prompt_uid")
    if prompt_uid:
        with st.container(border=True):
            st.markdown("**Tilføj til indkøbslisten igen?**")
            c1, c2, c3 = st.columns([0.5, 0.25, 0.25], gap="small")
            with c1:
                st.text_input("Antal", label_visibility="collapsed", placeholder="Antal", key="pantry_prompt_qty_text")
            with c2:
                if st.button("Ja", type="primary", key="pantry_yes"):
                    qty_used = _parse_qty(ss["pantry_prompt_qty_text"])
                    text = pantry_used_add_back(prompt_uid, qty_used)
                    if text:
                        add_shopping(text=text, qty=qty_used, category="Ukategoriseret")
                        sync_db()
                    ss["pantry_prompt_uid"] = None
                    ss["pantry_prompt_qty_text"] = "1"
                    st.rerun()
            with c3:
                if st.button("Nej", type="tertiary", key="pantry_no"):
                    ss["pantry_prompt_uid"] = None
                    ss["pantry_prompt_qty_text"] = "1"
                    st.rerun()

    pantry_rows = fetch_pantry()
    if not pantry_rows:
        st.info("Ingen varer registreret derhjemme endnu.")
    else:
        def loc_key(x: str):
            return ("zzzz" if x == "Ukategoriseret" else x.lower())

        locs = sorted({(r[3] or "Ukategoriseret") for r in pantry_rows}, key=loc_key)

        with st.container(gap=None, border=True):
            for loc in locs:
                group = [r for r in pantry_rows if (r[3] or "Ukategoriseret") == loc]
                if not group:
                    continue

                st.caption(loc)

                for uid, text, qty, location in group:
                    with st.container(horizontal=True, vertical_alignment="center"):
                        st.markdown(f"{_fmt_qty(qty)} × {text}")

                        sel_key = f"loc_{uid}"
                        if sel_key not in ss:
                            ss[sel_key] = location if location in ss["pantry_locations"] else "Ukategoriseret"

                        new_loc = st.selectbox(
                            "Placering",
                            options=ss["pantry_locations"],
                            key=sel_key,
                            label_visibility="collapsed",
                        )
                        if new_loc != location:
                            pantry_set_location(uid=uid, text=text, location=new_loc)
                            sync_db()
                            st.rerun()

                        if st.button("Brugt", key=f"used_{uid}", type="secondary"):
                            ss["pantry_prompt_uid"] = uid
                            ss["pantry_prompt_qty_text"] = "1"
                            st.rerun()
