# pages/Shopping.py
# -*- coding: utf-8 -*-
import datetime as _dt

import pandas as pd
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
    # Ugemenu / opskrifter
    add_recipe,
    delete_recipe,
    fetch_recipes,
    add_recipe_item,
    delete_recipe_item,
    fetch_recipe_items,
    set_meal_for_date,
    clear_meal_for_date,
    fetch_meal_plan,
    generate_shopping_from_mealplan,
)
import drive_sync

st.set_page_config(page_title=f"{APP_TITLE} • Shopping", page_icon="🛒", layout="centered")
st.link_button("⬅️ Tilbage til forside", "/", width="stretch")

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
ss.setdefault("show_add_to_menu", False)

with st.expander("Drive sync status", expanded=False):
    if drive is None:
        st.warning(f"Drive sync disabled (could not connect): {drive_error}")
    else:
        st.success("Drive connected ✅")
        if downloaded_db:
            st.info("Downloaded latest database from Drive ✅")

    ss["autosync"] = st.checkbox("Auto-sync til Drive", value=ss["autosync"])
    if st.button("Sync nu", type="tertiary", width="content"):
        try:
            drive_sync.upload_or_update(drive, drive_sync.FOLDER_ID, DB_PATH, DB_DRIVE_NAME)
            st.success("Synced ✅")
        except Exception as e:
            st.warning(f"Kunne ikke sync'e: {e}")


def sync_db():
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


def _monday(d: _dt.date) -> _dt.date:
    return d - _dt.timedelta(days=d.weekday())


def _iso(d: _dt.date) -> str:
    return d.isoformat()


def _clean_cat(cat: str) -> str:
    cat = (cat or "").strip()
    if not cat:
        return "Ukategoriseret"
    if cat.lower() == "ukategoret":
        return "Ukategoriseret"
    return cat


def _name_match(name: str, q: str) -> bool:
    q = (q or "").strip().lower()
    if not q:
        return True
    return q in (name or "").strip().lower()


def _default_recipe_df(n: int = 8) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "Vare": [""] * n,
            "Mængde": [1.0] * n,
            "Kategori": ["Ukategoriseret"] * n,
            "⭐": [False] * n,
        }
    )


def _sanitize_recipe_df(df: pd.DataFrame) -> list[dict]:
    """
    Rens input ved gem:
      - trim tekst
      - qty => float >= 1
      - kategori normaliseres
      - tomme rækker fjernes
    Return: list of dict {text, qty, cat, is_std}
    """
    if df is None or df.empty:
        return []
    out = []
    for _, row in df.iterrows():
        text = str(row.get("Vare", "") or "").strip()
        if not text:
            continue

        qty = row.get("Mængde", 1.0)
        try:
            qty = float(qty) if qty is not None else 1.0
        except Exception:
            qty = 1.0
        qty = 1.0 if qty <= 0 else qty

        cat = _clean_cat(row.get("Kategori", "Ukategoriseret"))
        is_std = 1 if bool(row.get("⭐", False)) else 0

        out.append({"text": text, "qty": qty, "cat": cat, "is_std": is_std})
    return out


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

tab_shop, tab_pantry, tab_menu, tab_recipes = st.tabs(["Indkøbsliste", "Hjemme", "Ugemenu", "Opskrifter"])

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
                index=ss["shopping_categories"].index("Ukategoriseret"),
                key="new_item_cat",
                label_visibility="collapsed",
            )
            st.checkbox("⭐", key="new_item_std", help="Markér som standardvare")
            submitted = st.form_submit_button("Tilføj", icon=":material/add:")

        if submitted:
            text = (ss.get("new_item_text") or "").strip()
            if text:
                qty = _parse_qty(ss.get("new_item_qty_text"))
                cat = _clean_cat(ss.get("new_item_cat") or "Ukategoriseret")
                is_std = 1 if ss.get("new_item_std") else 0
                add_shopping(text=text, qty=qty, category=cat, is_standard=is_std)
                if is_std:
                    upsert_standard(text=text, category=cat, default_qty=qty)
                sync_db()
                st.rerun()

    rows = fetch_shopping()
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

                        star_label = "⭐" if is_std else "☆"
                        if st.button(star_label, key=f"shop_star_{uid}", type="tertiary", help="Toggle standardvare", width="content"):
                            new_std = 0 if is_std else 1
                            info = set_shopping_standard(uid, new_std)
                            if info:
                                t, c, q = info
                                if new_std == 1:
                                    upsert_standard(t, c, q)
                                else:
                                    delete_standard(t)
                            sync_db()
                            st.rerun()

                        if st.button("Købt", key=f"shop_b_{uid}", type="secondary", width="content"):
                            popped = pop_shopping(uid)
                            if popped:
                                t, q, c, popped_std = popped
                                pantry_add_or_merge(t, q, c, is_standard=popped_std)
                            sync_db()
                            st.rerun()

                        if st.button(":material/delete:", key=f"shop_r_{uid}", type="tertiary", width="content"):
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
                index=ss["shopping_categories"].index("Ukategoriseret"),
                key="pantry_new_cat",
                label_visibility="collapsed",
            )
            st.checkbox("⭐", key="pantry_new_std", help="Markér som standardvare")
            submitted_pantry = st.form_submit_button("Tilføj", icon=":material/add:")

        if submitted_pantry:
            text = (ss.get("pantry_new_text") or "").strip()
            if text:
                qty = _parse_qty(ss.get("pantry_new_qty"))
                cat = _clean_cat(ss.get("pantry_new_cat") or "Ukategoriseret")
                is_std = 1 if ss.get("pantry_new_std") else 0
                pantry_add_or_merge(text, qty, cat, is_standard=is_std)
                if is_std:
                    upsert_standard(text=text, category=cat, default_qty=qty)
                sync_db()
                st.rerun()

    # Prompt when clicking "Brugt"
    prompt_uid = ss.get("pantry_prompt_uid")
    if prompt_uid:
        info = get_pantry_item(prompt_uid)
        if info:
            p_text, p_qty, p_cat, p_std = info
            default_key = f"used_qty_{prompt_uid}"
            if default_key not in ss:
                ss[default_key] = _fmt_qty(p_qty)

            with st.container(border=True):
                st.markdown(f"**Brugt: {p_text}** ({_fmt_qty(p_qty)} ×) \nTilføj til indkøbslisten igen?")
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
                        res = pantry_consume(prompt_uid, qty_used)
                        if res:
                            sync_db()
                        ss["pantry_prompt_uid"] = None
                        st.rerun()
        else:
            ss["pantry_prompt_uid"] = None

    pantry_rows = fetch_pantry()
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

                        star_label = "⭐" if is_std else "☆"
                        if st.button(star_label, key=f"pantry_star_{uid}", type="tertiary", help="Toggle standardvare", width="content"):
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

                        if _cat != "Frost":
                            if st.button("→ Frost", key=f"to_frost_{uid}", type="tertiary", width="content"):
                                changed = pantry_move_category(uid, "Frost")
                                if changed:
                                    sync_db()
                                    st.rerun()

                        if st.button("Brugt", key=f"used_{uid}", type="secondary", width="content"):
                            ss["pantry_prompt_uid"] = uid
                            ss[f"used_qty_{uid}"] = _fmt_qty(qty)
                            st.rerun()

    # Standard box
    standards = fetch_standards()
    if standards:
        missing, present = [], []
        for text, cat, default_qty in standards:
            k = (text or "").strip().lower()
            in_home = k in pantry_textkeys
            in_shop = k in shopping_textkeys
            status = "⚠️ Mangler"
            if in_home and in_shop:
                status = "✅ Hjemme • 🛒 På liste"
            elif in_home:
                status = "✅ Hjemme"
            elif in_shop:
                status = "🛒 På liste"

            row = (text, cat, default_qty, k, in_shop, status)
            (missing if status == "⚠️ Mangler" else present).append(row)

        st.divider()
        with st.container(border=True):
            st.subheader("⭐ Standardvarer")

            if missing:
                st.markdown("**⚠️ Mangler**")
                for text, cat, default_qty, k, in_shop, status in missing:
                    left, right = st.columns([4, 1], vertical_alignment="center")
                    with left:
                        st.markdown(f"**{text}** \n:small[{cat} • {status}]")
                    with right:
                        if st.button("Tilføj", key=f"std_add_missing_{k}", width="content"):
                            add_shopping(text=text, qty=default_qty, category=cat, is_standard=1)
                            sync_db()
                            st.rerun()
                st.markdown("---")

            st.markdown("**Resten**")
            for text, cat, default_qty, k, in_shop, status in present:
                left, right = st.columns([4, 1], vertical_alignment="center")
                with left:
                    st.markdown(f"**{text}** \n:small[{cat} • {status}]")
                with right:
                    disabled = in_shop
                    if st.button(
                        "Tilføj",
                        key=f"std_add_present_{k}",
                        disabled=disabled,
                        help="Tilføj direkte til indkøbslisten" if not disabled else "Allerede på indkøbslisten",
                        width="content",
                    ):
                        add_shopping(text=text, qty=default_qty, category=cat, is_standard=1)
                        sync_db()
                        st.rerun()

# -----------------------------
# TAB: Ugemenu (plan + generér + hurtigsæt)
# -----------------------------
with tab_menu:
    st.subheader("📅 Ugemenu")

    today = _dt.date.today()
    week_start = st.date_input("Vælg uge (mandag)", value=_monday(today), key="menu_week_start_input")
    week_start = _monday(week_start)
    ss["menu_week_start_iso"] = _iso(week_start)

    week_dates = [week_start + _dt.timedelta(days=i) for i in range(7)]
    week_from = _iso(week_dates[0])
    week_to = _iso(week_dates[-1])

    all_recipes = fetch_recipes()
    recipe_name_by_uid = {uid: name for uid, name in all_recipes}

    ss.setdefault("menu_recipe_search", "")
    q = st.text_input("Søg opskrift", value=ss["menu_recipe_search"], placeholder="Søg…", key="menu_recipe_search")

    filtered = [(uid, name) for uid, name in all_recipes if _name_match(name, q)]
    recipe_uids_filtered = [""] + [uid for uid, _ in filtered]
    recipe_uids_all = [""] + [uid for uid, _ in all_recipes]

    with st.container(border=True):
        st.markdown("### ⚡ Hurtigsæt")
        c1, c2, c3, c4 = st.columns([1.4, 2.4, 1.0, 1.2], vertical_alignment="center")

        with c1:
            day_labels = [d.strftime("%a %d/%m") for d in week_dates]
            day_idx = st.selectbox(
                "Dag",
                options=list(range(7)),
                format_func=lambda i: day_labels[i],
                key="quick_day",
                label_visibility="collapsed",
            )
        with c2:
            quick_uid = st.selectbox(
                "Opskrift",
                options=recipe_uids_filtered,
                format_func=lambda u: ("— vælg opskrift —" if u == "" else recipe_name_by_uid.get(u, u)),
                key="quick_recipe_uid",
                label_visibility="collapsed",
            )
        with c3:
            st.text_input("Antal", key="quick_servings", value="1", label_visibility="collapsed", placeholder="1")
        with c4:
            if st.button("Sæt", type="primary", width="stretch", key="quick_set_btn"):
                if quick_uid == "":
                    st.warning("Vælg en opskrift.")
                else:
                    raw = (ss.get("quick_servings") or "").strip().replace(",", ".")
                    try:
                        servings = float(raw) if raw else 1.0
                    except Exception:
                        servings = 1.0
                    servings = 1.0 if servings <= 0 else servings

                    d = week_dates[int(day_idx)]
                    d_str = _iso(d)
                    title = recipe_name_by_uid.get(quick_uid, "")
                    set_meal_for_date(d_str, quick_uid, title, servings=servings, note="")
                    sync_db()
                    st.success(f"Satte **{title}** på {d.strftime('%a %d/%m')}.")
                    st.rerun()

    plan_rows = fetch_meal_plan(week_from, week_to)
    plan_by_date = {d: (ruid, title, servings, note) for (d, ruid, title, servings, note) in plan_rows}

    st.caption("Planlæg 7 dage. Brug hurtigsæt eller redigér manuelt nedenfor.")

    with st.container(border=True):
        for d in week_dates:
            d_str = _iso(d)
            ruid, title, servings, note = plan_by_date.get(d_str, (None, "", 1.0, ""))

            row_cols = st.columns([1.25, 2.4, 1.1, 0.8], vertical_alignment="center")
            with row_cols[0]:
                st.markdown(f"**{d.strftime('%a %d/%m')}**")

            with row_cols[1]:
                current_uid = ruid or ""
                options = recipe_uids_all if not q.strip() else recipe_uids_filtered
                idx = options.index(current_uid) if current_uid in options else 0

                chosen_uid = st.selectbox(
                    "Opskrift",
                    options=options,
                    format_func=lambda u: ("— vælg opskrift —" if u == "" else recipe_name_by_uid.get(u, u)),
                    index=idx,
                    key=f"mp_recipe_{d_str}",
                    label_visibility="collapsed",
                )

            with row_cols[2]:
                st.text_input("Titel", value=(title or ""), key=f"mp_title_{d_str}", label_visibility="collapsed", placeholder="fx Rester…")

            with row_cols[3]:
                st.text_input(
                    "Antal",
                    value=str(int(servings)) if float(servings).is_integer() else str(servings),
                    key=f"mp_serv_{d_str}",
                    label_visibility="collapsed",
                    placeholder="1",
                )

            st.text_input(f"Note {d_str}", value=(note or ""), key=f"mp_note_{d_str}", label_visibility="collapsed", placeholder="Note (valgfri)…")

            bcols = st.columns([1, 1, 6], vertical_alignment="center")
            with bcols[0]:
                if st.button("Gem", key=f"mp_save_{d_str}", type="secondary", width="content"):
                    raw = (ss.get(f"mp_serv_{d_str}") or "").strip().replace(",", ".")
                    try:
                        s = float(raw) if raw else 1.0
                    except Exception:
                        s = 1.0
                    s = 1.0 if s <= 0 else s

                    t = (ss.get(f"mp_title_{d_str}") or "").strip()
                    n = (ss.get(f"mp_note_{d_str}") or "").strip()
                    cu = chosen_uid if chosen_uid != "" else None

                    if cu is None and not t:
                        clear_meal_for_date(d_str)
                    else:
                        if cu is not None and not t:
                            t = recipe_name_by_uid.get(cu, "")
                        set_meal_for_date(d_str, cu, t, servings=s, note=n)

                    sync_db()
                    st.rerun()

            with bcols[1]:
                if st.button("Ryd", key=f"mp_clear_{d_str}", type="tertiary", width="content"):
                    clear_meal_for_date(d_str)
                    sync_db()
                    st.rerun()

    st.divider()
    left, right = st.columns([2, 1], vertical_alignment="center")
    with left:
        check_home = st.checkbox("Tjek hjemme først (tilføj kun mangler)", value=True)
    with right:
        if st.button("🛒 Generér indkøbsliste", type="primary", width="stretch"):
            summary = generate_shopping_from_mealplan(week_from, week_to, check_pantry_first=check_home)
            sync_db()
            st.success(
                f"Tilføjet {summary.get('added',0)} vare(r). "
                f"Samlet: {summary.get('merged_items',0)}. "
                f"Springet over (hjemme-match): {summary.get('skipped_home',0)}."
            )
            st.rerun()

# -----------------------------
# TAB: Opskrifter (hurtigsøg + bulk + kopi + tilføj til ugemenu)
# -----------------------------
with tab_recipes:
    st.subheader("📚 Opskriftbibliotek")

    all_recipes = fetch_recipes()
    recipe_name_by_uid = {uid: name for uid, name in all_recipes}

    ss.setdefault("recipe_search", "")
    search = st.text_input("Hurtigsøg", value=ss["recipe_search"], placeholder="Søg opskrift…", key="recipe_search")

    recipes = [(uid, name) for uid, name in all_recipes if _name_match(name, search)]

    # ---------- Ny opskrift (bulk) ----------
    with st.container(border=True):
        st.markdown("### ➕ Ny opskrift")

        ss.setdefault("new_recipe_name", "")
        ss.setdefault("new_recipe_df", _default_recipe_df(8))

        top = st.columns([3, 1, 1], vertical_alignment="center")
        with top[0]:
            ss["new_recipe_name"] = st.text_input(
                "Navn på ret",
                value=ss["new_recipe_name"],
                placeholder="Fx Lasagne",
                label_visibility="collapsed",
                key="new_recipe_name_input",
            )
        with top[1]:
            if st.button("+ Tilføj 5 rækker", type="tertiary", key="new_recipe_add_rows", width="content"):
                ss["new_recipe_df"] = pd.concat([ss["new_recipe_df"], _default_recipe_df(5)], ignore_index=True)
                st.rerun()
        with top[2]:
            if st.button("Nulstil", type="tertiary", key="new_recipe_reset", width="content"):
                ss["new_recipe_name"] = ""
                ss["new_recipe_df"] = _default_recipe_df(8)
                st.rerun()

        edited_df = st.data_editor(
            ss["new_recipe_df"],
            key="new_recipe_editor_widget",  # widget-key (må IKKE skrives til direkte)
            num_rows="dynamic",
            width="stretch",
            column_config={
                "Vare": st.column_config.TextColumn(required=False),
                "Mængde": st.column_config.NumberColumn(min_value=0.0, step=1.0),
                "Kategori": st.column_config.SelectboxColumn(options=ss["shopping_categories"]),
                "⭐": st.column_config.CheckboxColumn(help="Markér ingrediens som standardvare"),
            },
        )
        ss["new_recipe_df"] = edited_df  # state-key (ok)

        preview = _sanitize_recipe_df(edited_df)
        if preview:
            with st.expander("Preview (det der gemmes)", expanded=True):
                for r in preview:
                    st.markdown(f"- {_fmt_qty(r['qty'])} × **{r['text']}**  :small[{r['cat']}{' • ⭐' if r['is_std'] else ''}]")
        else:
            st.caption("Preview: ingen ingredienser endnu.")

        if st.button("Tilføj opskrift", type="primary", width="stretch", key="save_new_recipe_once"):
            name = (ss.get("new_recipe_name") or "").strip()
            if not name:
                st.warning("Skriv et navn på retten.")
            else:
                ruid = add_recipe(name)
                if not ruid:
                    st.warning("Kunne ikke oprette opskriften.")
                else:
                    for r in preview:
                        add_recipe_item(ruid, r["text"], r["qty"], r["cat"], is_standard=r["is_std"])
                        if r["is_std"]:
                            upsert_standard(text=r["text"], category=r["cat"], default_qty=r["qty"])

                    sync_db()
                    ss["new_recipe_name"] = ""
                    ss["new_recipe_df"] = _default_recipe_df(8)
                    st.success(f"Gemte opskrift: {name} ✅")
                    st.rerun()

    st.divider()

    # ---------- Redigér / Kopiér / Tilføj til ugemenu ----------
    if not all_recipes:
        st.info("Ingen opskrifter endnu.")
    elif not recipes:
        st.warning("Ingen opskrifter matcher din søgning.")
    else:
        ruids = [uid for uid, _ in recipes]
        ss.setdefault("recipe_edit_uid_tab", ruids[0])
        if ss["recipe_edit_uid_tab"] not in ruids:
            ss["recipe_edit_uid_tab"] = ruids[0]

        chosen = st.selectbox(
            "Vælg opskrift",
            options=ruids,
            format_func=lambda u: recipe_name_by_uid.get(u, u),
            key="recipe_edit_uid_tab",
        )

        # Data-key og widget-key adskilt
        df_key = f"recipe_edit_df_{chosen}"
        widget_key = f"recipe_edit_editor_{chosen}"

        if df_key not in ss:
            items = fetch_recipe_items(chosen)  # (uid,text,qty,cat,is_std)
            ss[df_key] = pd.DataFrame(
                {
                    "Vare": [t for (_uid, t, _q, _c, _s) in items],
                    "Mængde": [float(q) for (_uid, _t, q, _c, _s) in items],
                    "Kategori": [(_c or "Ukategoriseret") for (_uid, _t, _q, _c, _s) in items],
                    "⭐": [bool(s) for (_uid, _t, _q, _c, s) in items],
                }
            )
            if ss[df_key].empty:
                ss[df_key] = _default_recipe_df(8)

        with st.container(border=True):
            st.markdown(f"### ✏️ Redigér: **{recipe_name_by_uid.get(chosen,'')}**")

            c1, c2, c3, c4, c5 = st.columns([1, 1, 1, 1.2, 2.8], vertical_alignment="center")

            with c1:
                if st.button("Slet", type="tertiary", key="delete_recipe_btn_tab", width="content"):
                    delete_recipe(chosen)
                    sync_db()
                    # ryd cache
                    if df_key in ss:
                        del ss[df_key]
                    st.rerun()

            with c2:
                if st.button("Kopiér", type="secondary", key="copy_recipe_btn_tab", width="content"):
                    original_name = recipe_name_by_uid.get(chosen, "Opskrift")
                    new_name = f"{original_name} (kopi)"
                    new_uid = add_recipe(new_name)
                    if new_uid:
                        for _uid, t, q, cat, is_std in fetch_recipe_items(chosen):
                            add_recipe_item(new_uid, t, q, cat, is_standard=int(is_std or 0))
                        sync_db()
                        ss["recipe_edit_uid_tab"] = new_uid
                        st.success("Kopieret ✅")
                        st.rerun()
                    else:
                        st.warning("Kunne ikke kopiere opskrift.")

            with c3:
                if st.button("+ 5 rækker", type="tertiary", key="edit_add_rows_btn", width="content"):
                    ss[df_key] = pd.concat([ss[df_key], _default_recipe_df(5)], ignore_index=True)
                    st.rerun()

            with c4:
                if st.button("➕ Ugemenu", type="primary", key="add_to_menu_btn", width="content"):
                    ss["show_add_to_menu"] = True

            with c5:
                st.caption("Tip: Redigér i tabellen og gem én gang.")

            # Add-to-menu panel
            if ss.get("show_add_to_menu", False):
                ws_iso = ss.get("menu_week_start_iso")
                ws = _dt.date.fromisoformat(ws_iso) if ws_iso else _monday(_dt.date.today())
                wdays = [ws + _dt.timedelta(days=i) for i in range(7)]
                labels = [d.strftime("%a %d/%m") for d in wdays]

                with st.container(border=True):
                    st.markdown("**Tilføj til ugemenu**")
                    m1, m2, m3, m4 = st.columns([1.4, 0.8, 2.2, 1.0], vertical_alignment="center")
                    with m1:
                        day_i = st.selectbox(
                            "Dag", options=list(range(7)), format_func=lambda i: labels[i],
                            key="add_menu_day", label_visibility="collapsed"
                        )
                    with m2:
                        st.text_input("Antal", key="add_menu_serv", value="1", label_visibility="collapsed")
                    with m3:
                        st.text_input("Note", key="add_menu_note", value="", placeholder="Note (valgfri)…", label_visibility="collapsed")
                    with m4:
                        if st.button("Sæt", key="add_menu_confirm", type="secondary", width="stretch"):
                            raw = (ss.get("add_menu_serv") or "").strip().replace(",", ".")
                            try:
                                s = float(raw) if raw else 1.0
                            except Exception:
                                s = 1.0
                            s = 1.0 if s <= 0 else s
                            d = wdays[int(day_i)]
                            title = recipe_name_by_uid.get(chosen, "")
                            set_meal_for_date(_iso(d), chosen, title, servings=s, note=(ss.get("add_menu_note") or "").strip())
                            sync_db()
                            ss["show_add_to_menu"] = False
                            st.success(f"Tilføjet **{title}** til {d.strftime('%a %d/%m')}.")
                            st.rerun()

                    if st.button("Luk", key="add_menu_close", type="tertiary", width="content"):
                        ss["show_add_to_menu"] = False
                        st.rerun()

            # Data editor (DF) – widget key er adskilt fra df_key
            edited = st.data_editor(
                ss[df_key],
                key=widget_key,
                num_rows="dynamic",
                width="stretch",
                column_config={
                    "Vare": st.column_config.TextColumn(required=False),
                    "Mængde": st.column_config.NumberColumn(min_value=0.0, step=1.0),
                    "Kategori": st.column_config.SelectboxColumn(options=ss["shopping_categories"]),
                    "⭐": st.column_config.CheckboxColumn(help="Markér ingrediens som standardvare"),
                },
            )
            ss[df_key] = edited

            preview_edit = _sanitize_recipe_df(edited)
            if preview_edit:
                with st.expander("Preview (det der gemmes)", expanded=False):
                    for r in preview_edit:
                        st.markdown(f"- {_fmt_qty(r['qty'])} × **{r['text']}**  :small[{r['cat']}{' • ⭐' if r['is_std'] else ''}]")

            if st.button("Gem ændringer", type="primary", width="stretch", key="save_recipe_changes_btn"):
                # Replace-liste: slet gamle og indsæt nye
                for uid, _t, _q, _c, _std in fetch_recipe_items(chosen):
                    delete_recipe_item(uid)

                for r in preview_edit:
                    add_recipe_item(chosen, r["text"], r["qty"], r["cat"], is_standard=r["is_std"])
                    if r["is_std"]:
                        upsert_standard(text=r["text"], category=r["cat"], default_qty=r["qty"])

                sync_db()
                # Drop cached DF so it reloads from DB cleanly on rerun
                if df_key in ss:
                    del ss[df_key]
                st.success("Gemte ændringer ✅")
                st.rerun()
