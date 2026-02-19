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
    pantry_used_add_back,
)

import drive_sync  # robust import


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


def _sorted_categories(rows):
    # rows: list of (uid,text,qty,category)
    def key(c: str):
        return ("zzzz" if c == "Ukategoriseret" else c.lower())
    return sorted({(r[3] or "Ukategoriseret") for r in rows}, key=key)


ss = st.session_state
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

# prompt state for "Brugt"
ss.setdefault("pantry_prompt_uid", None)

tab_shop, tab_pantry = st.tabs(["Indkøbsliste", "Hjemme"])

# -----------------------------
# TAB: Indkøbsliste
# -----------------------------
with tab_shop:
    # Tilføj vare (kompakt, mobilvenlig)
    with st.form("add_item_form", border=False, clear_on_submit=True):
        with st.container(horizontal=True, vertical_alignment="bottom"):
            st.text_input("Vare", label_visibility="collapsed", placeholder="Tilføj vare…", key="new_item_text")
            st.text_input("Antal", label_visibility="collapsed", placeholder="Antal", key="new_item_qty_text")
            st.selectbox(
                "Kategori",
                ss["shopping_categories"],
                index=ss["shopping_categories"].index("Ukategoriseret")
                if "Ukategoriseret" in ss["shopping_categories"]
                else 0,
                key="new_item_cat",
                label_visibility="collapsed",
            )
            submitted = st.form_submit_button("Tilføj", icon=":material/add:")

        if submitted:
            text = (ss.get("new_item_text") or "").strip()
            if text:
                qty = _parse_qty(ss.get("new_item_qty_text"))
                cat = (ss.get("new_item_cat") or "Ukategoriseret").strip() or "Ukategoriseret"
                add_shopping(text=text, qty=qty, category=cat)
                sync_db()
            st.rerun()

    # Liste i bokse pr kategori
    rows = fetch_shopping()
    if not rows:
        st.info("Listen er tom.")
    else:
        for cat in _sorted_categories(rows):
            group = [r for r in rows if (r[3] or "Ukategoriseret") == cat]
            if not group:
                continue

            with st.container(border=True):
                st.caption(cat)

                for uid, text, qty, _cat in group:
                    with st.container(horizontal=True, vertical_alignment="center"):
                        st.markdown(f"{_fmt_qty(qty)} × {text}")

                        if st.button("Købt", key=f"shop_b_{uid}", type="secondary"):
                            popped = pop_shopping(uid)
                            if popped:
                                t, q, c = popped
                                pantry_add_or_merge(t, q, c)  # samme kategori som i indkøbslisten
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
    # Tilføj direkte i Hjemme (rester til fryseren osv.)
    st.caption("Tilføj direkte til det du har derhjemme")
    with st.form("add_pantry_form", border=False, clear_on_submit=True):
        with st.container(horizontal=True, vertical_alignment="bottom"):
            st.text_input("Vare", label_visibility="collapsed", placeholder="Tilføj til hjemme…", key="pantry_new_text")
            st.text_input("Antal", label_visibility="collapsed", placeholder="Antal", key="pantry_new_qty")
            st.selectbox(
                "Kategori",
                ss["shopping_categories"],
                index=ss["shopping_categories"].index("Ukategoriseret")
                if "Ukategoriseret" in ss["shopping_categories"]
                else 0,
                key="pantry_new_cat",
                label_visibility="collapsed",
            )
            submitted_pantry = st.form_submit_button("Tilføj", icon=":material/add:")

        if submitted_pantry:
            text = (ss.get("pantry_new_text") or "").strip()
            if text:
                qty = _parse_qty(ss.get("pantry_new_qty"))
                cat = (ss.get("pantry_new_cat") or "Ukategoriseret").strip() or "Ukategoriseret"
                pantry_add_or_merge(text, qty, cat)
                sync_db()
            st.rerun()

    # Prompt for "Brugt" (fixer session_state-fejlen ved at bruge form)
    prompt_uid = ss.get("pantry_prompt_uid")
    if prompt_uid:
        with st.container(border=True):
            st.markdown("**Tilføj til indkøbslisten igen?**")

            # unikt form-key per prompt_uid så clear_on_submit altid virker rent
            with st.form(f"used_prompt_form_{prompt_uid}", clear_on_submit=True, border=False):
                c1, c2, c3 = st.columns([0.5, 0.25, 0.25], gap="small")
                with c1:
                    st.text_input("Antal", label_visibility="collapsed", placeholder="Antal", key=f"used_qty_{prompt_uid}")
                with c2:
                    yes = st.form_submit_button("Ja")
                with c3:
                    no = st.form_submit_button("Nej")

                if yes:
                    qty_used = _parse_qty(ss.get(f"used_qty_{prompt_uid}"))
                    result = pantry_used_add_back(prompt_uid, qty_used)
                    if result:
                        text, cat = result
                        add_shopping(text=text, qty=qty_used, category=cat)  # samme kategori
                        sync_db()
                    ss["pantry_prompt_uid"] = None
                    st.rerun()

                if no:
                    ss["pantry_prompt_uid"] = None
                    st.rerun()

    # Hjemme-liste i bokse pr kategori
    pantry_rows = fetch_pantry()
    if not pantry_rows:
        st.info("Ingen varer registreret derhjemme endnu.")
    else:
        for cat in _sorted_categories(pantry_rows):
            group = [r for r in pantry_rows if (r[3] or "Ukategoriseret") == cat]
            if not group:
                continue

            with st.container(border=True):
                st.caption(cat)

                for uid, text, qty, _cat in group:
                    with st.container(horizontal=True, vertical_alignment="center"):
                        st.markdown(f"{_fmt_qty(qty)} × {text}")

                        if st.button("Brugt", key=f"used_{uid}", type="secondary"):
                            ss["pantry_prompt_uid"] = uid
                            st.rerun()
