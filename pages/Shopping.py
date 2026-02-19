# pages/Shopping.py
# -*- coding: utf-8 -*-
import streamlit as st

from src.app_state import init_app_state
from src.config import APP_TITLE, DB_PATH, DB_DRIVE_NAME
from src.storage_shopping import (
    init_shopping_tables,
    fetch_shopping,
    fetch_pantry,
    fetch_standards,
    upsert_standard,
    delete_standard,
    add_shopping,
    delete_shopping,
    pop_shopping,
    pantry_add_or_merge,
    get_pantry_item,
    pantry_consume,
    pantry_move_category,
    set_shopping_standard,
    set_pantry_standard,
)

import drive_sync

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

ss = st.session_state
ss.setdefault("autosync", True)
ss.setdefault("pantry_prompt_uid", None)

with st.expander("Drive sync status", expanded=False):
    if drive is None:
        st.warning(f"Drive sync disabled (could not connect): {drive_error}")
    else:
        st.success("Drive connected ✅")
        if downloaded_db:
            st.info("Downloaded latest database from Drive ✅")

        ss["autosync"] = st.checkbox("Auto-sync til Drive", value=ss["autosync"])
        if st.button("Sync nu", type="tertiary"):
            try:
                drive_sync.upload_or_update(drive, drive_sync.FOLDER_ID, DB_PATH, DB_DRIVE_NAME)
                st.success("Synced ✅")
            except Exception as e:
                st.warning(f"Kunne ikke sync'e: {e}")


def sync_db():
    # Speed: allow turning autosync off (so clicks feel instant)
    if drive is None or not ss.get("autosync", True):
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


def _sorted_categories(rows, idx_cat: int):
    def key(c: str):
        return ("zzzz" if c == "Ukategoriseret" else c.lower())
    return sorted({(r[idx_cat] or "Ukategoriseret") for r in rows}, key=key)


ss.setdefault(
    "shopping_categories",
    [
        "Frugt & grønt",
        "Kød & fisk",
        "Mejeri",
        "Brød",
        "Kolonial",
        "Frost",
        "Drikkevarer",
        "Diverse",
        "Ukategoriseret",
    ],
)

tab_shop, tab_pantry = st.tabs(["Indkøbsliste", "Hjemme"])

# -----------------------------
# TAB: Indkøbsliste
# -----------------------------
with tab_shop:
    with st.form("add_item_form", border=False, clear_on_submit=True):
        with st.container(horizontal=True, vertical_alignment="bottom"):
            st.text_input("Vare", label_visibility="collapsed", placeholder="Tilføj vare…", key="new_item_text")
            st.text_input("Antal", label_visibility="collapsed", placeholder="Antal", key="new_item_qty_text")
            st.selectbox(
                "Kategori",
                ss["shopping_categories"],
                index=ss["shopping_categories"].index("Ukategoriseret")
                if "Ukategoriseret" in ss["shopping_categories"] else 0,
                key="new_item_cat",
                label_visibility="collapsed",
            )
            st.checkbox("⭐", key="new_item_std", help="Markér som standardvare")
            submitted = st.form_submit_button("Tilføj", icon=":material/add:")

        if submitted:
            text = (ss.get("new_item_text") or "").strip()
            if text:
                qty = _parse_qty(ss.get("new_item_qty_text"))
                cat = (ss.get("new_item_cat") or "Ukategoriseret").strip() or "Ukategoriseret"
                is_std = 1 if ss.get("new_item_std") else 0

                add_shopping(text=text, qty=qty, category=cat, is_standard=is_std)
                if is_std:
                    upsert_standard(text=text, category=cat, default_qty=qty)
                sync_db()
            st.rerun()

    rows = fetch_shopping()  # (uid,text,qty,cat,is_std)
    if not rows:
        st.info("Listen er tom.")
    else:
        for cat in _sorted_categories(rows, idx_cat=3):
            group = [r for r in rows if (r[3] or "Ukategoriseret") == cat]
            if not group:
                continue

            with st.container(border=True):
                st.caption(cat)

                for uid, text, qty, _cat, is_std in group:
                    with st.container(horizontal=True, vertical_alignment="center"):
                        st.markdown(f"{_fmt_qty(qty)} × {text}")

                        # ⭐ toggle (remove / add standard)
                        star_label = "⭐" if is_std else "☆"
                        if st.button(star_label, key=f"shop_star_{uid}", type="tertiary", help="Toggle standardvare"):
                            new_std = 0 if is_std else 1
                            info = set_shopping_standard(uid, new_std)
                            if info:
                                t, c, q = info
                                if new_std == 1:
                                    upsert_standard(t, c, q)
                                else:
                                    # removing standard removes it from catalog
                                    delete_standard(t)
                                sync_db()
                            st.rerun()

                        if st.button("Købt", key=f"shop_b_{uid}", type="secondary"):
                            popped = pop_shopping(uid)
                            if popped:
                                t, q, c, popped_std = popped
                                pantry_add_or_merge(t, q, c, is_standard=popped_std)
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
    st.caption("Tilføj direkte til det du har derhjemme (rester til fryseren osv.)")

    with st.form("add_pantry_form", border=False, clear_on_submit=True):
        with st.container(horizontal=True, vertical_alignment="bottom"):
            st.text_input("Vare", label_visibility="collapsed", placeholder="Tilføj til hjemme…", key="pantry_new_text")
            st.text_input("Antal", label_visibility="collapsed", placeholder="Antal", key="pantry_new_qty")
            st.selectbox(
                "Kategori",
                ss["shopping_categories"],
                index=ss["shopping_categories"].index("Ukategoriseret")
                if "Ukategoriseret" in ss["shopping_categories"] else 0,
                key="pantry_new_cat",
                label_visibility="collapsed",
            )
            st.checkbox("⭐", key="pantry_new_std", help="Markér som standardvare")
            submitted_pantry = st.form_submit_button("Tilføj", icon=":material/add:")

        if submitted_pantry:
            text = (ss.get("pantry_new_text") or "").strip()
            if text:
                qty = _parse_qty(ss.get("pantry_new_qty"))
                cat = (ss.get("pantry_new_cat") or "Ukategoriseret").strip() or "Ukategoriseret"
                is_std = 1 if ss.get("pantry_new_std") else 0

                pantry_add_or_merge(text, qty, cat, is_standard=is_std)
                if is_std:
                    upsert_standard(text=text, category=cat, default_qty=qty)
                sync_db()
            st.rerun()

    # Prompt when clicking "Brugt"
    prompt_uid = ss.get("pantry_prompt_uid")
    if prompt_uid:
        info = get_pantry_item(prompt_uid)  # (text, qty, cat, is_std)
        if info:
            p_text, p_qty, p_cat, p_std = info
            default_key = f"used_qty_{prompt_uid}"
            if default_key not in ss:
                ss[default_key] = _fmt_qty(p_qty)

            with st.container(border=True):
                st.markdown(f"**Brugt: {p_text}** ({_fmt_qty(p_qty)} ×)  \nTilføj til indkøbslisten igen?")

                with st.form(f"used_prompt_form_{prompt_uid}", clear_on_submit=True, border=False):
                    c1, c2, c3 = st.columns([0.5, 0.25, 0.25], gap="small")
                    with c1:
                        st.text_input("Antal", label_visibility="collapsed", placeholder="Antal", key=default_key)
                    with c2:
                        yes = st.form_submit_button("Ja")
                    with c3:
                        no = st.form_submit_button("Nej")

                    qty_used = _parse_qty(ss.get(default_key))

                    if yes:
                        res = pantry_consume(prompt_uid, qty_used)
                        if res:
                            t, c, is_std = res
                            add_shopping(text=t, qty=qty_used, category=c, is_standard=is_std)
                            if is_std:
                                upsert_standard(t, c, qty_used)
                            sync_db()
                        ss["pantry_prompt_uid"] = None
                        st.rerun()

                    if no:
                        # consume and don't add back
                        res = pantry_consume(prompt_uid, qty_used)
                        if res:
                            sync_db()
                        ss["pantry_prompt_uid"] = None
                        st.rerun()
        else:
            ss["pantry_prompt_uid"] = None

    pantry_rows = fetch_pantry()  # (uid,text,qty,cat,is_std)

    # Build sets for standard status without extra DB queries (speed)
    pantry_textkeys = {t.strip().lower() for (_, t, _, _, _) in pantry_rows} if pantry_rows else set()
    shopping_rows_now = fetch_shopping()
    shopping_textkeys = {t.strip().lower() for (_, t, _, _, _) in shopping_rows_now} if shopping_rows_now else set()

    if not pantry_rows:
        st.info("Ingen varer registreret derhjemme endnu.")
    else:
        for cat in _sorted_categories(pantry_rows, idx_cat=3):
            group = [r for r in pantry_rows if (r[3] or "Ukategoriseret") == cat]
            if not group:
                continue

            with st.container(border=True):
                st.caption(cat)

                for uid, text, qty, _cat, is_std in group:
                    with st.container(horizontal=True, vertical_alignment="center"):
                        st.markdown(f"{_fmt_qty(qty)} × {text}")

                        # ⭐ toggle
                        star_label = "⭐" if is_std else "☆"
                        if st.button(star_label, key=f"pantry_star_{uid}", type="tertiary", help="Toggle standardvare"):
                            new_std = 0 if is_std else 1
                            info2 = set_pantry_standard(uid, new_std)
                            if info2:
                                t, c, q = info2
                                if new_std == 1:
                                    upsert_standard(t, c, q)
                                else:
                                    delete_standard(t)
                                sync_db()
                            st.rerun()

                        # Quick move to Frost
                        if _cat != "Frost":
                            if st.button("→ Frost", key=f"to_frost_{uid}", type="tertiary"):
                                changed = pantry_move_category(uid, "Frost")
                                if changed:
                                    sync_db()
                                st.rerun()

                        if st.button("Brugt", key=f"used_{uid}", type="secondary"):
                            ss["pantry_prompt_uid"] = uid
                            ss[f"used_qty_{uid}"] = _fmt_qty(qty)
                            st.rerun()

    # Standard box (split missing / rest) – using already-built sets (speed)
    standards = fetch_standards()  # (text, category, default_qty)
    if standards:
        missing = []
        present = []
        for text, cat, default_qty in standards:
            k = (text or "").strip().lower()
            in_home = k in pantry_textkeys
            in_shop = k in shopping_textkeys

            if in_home and in_shop:
                status = "✅ Hjemme • 🛒 På liste"
            elif in_home:
                status = "✅ Hjemme"
            elif in_shop:
                status = "🛒 På liste"
            else:
                status = "⚠️ Mangler"

            row = (text, cat, default_qty, k, in_shop, status)
            if status == "⚠️ Mangler":
                missing.append(row)
            else:
                present.append(row)

        st.divider()
        with st.container(border=True):
            st.subheader("⭐ Standardvarer")

            if missing:
                st.markdown("**⚠️ Mangler**")
                for text, cat, default_qty, k, in_shop, status in missing:
                    left, right = st.columns([4, 1], vertical_alignment="center")
                    with left:
                        st.markdown(f"**{text}**  \n:small[{cat} • {status}]")
                    with right:
                        if st.button("Tilføj", key=f"std_add_missing_{k}"):
                            add_shopping(text=text, qty=default_qty, category=cat, is_standard=1)
                            sync_db()
                            st.rerun()
                st.markdown("---")

            st.markdown("**Resten**")
            for text, cat, default_qty, k, in_shop, status in present:
                left, right = st.columns([4, 1], vertical_alignment="center")
                with left:
                    st.markdown(f"**{text}**  \n:small[{cat} • {status}]")
                with right:
                    disabled = in_shop
                    if st.button(
                        "Tilføj",
                        key=f"std_add_present_{k}",
                        disabled=disabled,
                        help="Tilføj direkte til indkøbslisten" if not disabled else "Allerede på indkøbslisten",
                    ):
                        add_shopping(text=text, qty=default_qty, category=cat, is_standard=1)
                        sync_db()
                        st.rerun()
