# pages/Shopping.py
# -*- coding: utf-8 -*-
import datetime as _dt
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
    set_recipe_item_standard,
    set_meal_for_date,
    clear_meal_for_date,
    fetch_meal_plan,
    generate_shopping_from_mealplan,
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


def _monday(d: _dt.date) -> _dt.date:
    return d - _dt.timedelta(days=d.weekday())


def _iso(d: _dt.date) -> str:
    return d.isoformat()


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

tab_shop, tab_pantry, tab_menu = st.tabs(["Indkøbsliste", "Hjemme", "Ugemenu"])

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
                if "Ukategoriseret" in ss["shopping_categories"]
                else 0,
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
                        if st.button(
                            star_label,
                            key=f"shop_star_{uid}",
                            type="tertiary",
                            help="Toggle standardvare",
                        ):
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
                if "Ukategoriseret" in ss["shopping_categories"]
                else 0,
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
                        if st.button(
                            star_label,
                            key=f"pantry_star_{uid}",
                            type="tertiary",
                            help="Toggle standardvare",
                        ):
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
                        st.markdown(f"**{text}** \n:small[{cat} • {status}]")
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
                    st.markdown(f"**{text}** \n:small[{cat} • {status}]")
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

# -----------------------------
# TAB: Ugemenu
# -----------------------------
with tab_menu:
    st.subheader("📅 Ugemenu")

    # Week selector
    today = _dt.date.today()
    week_start = st.date_input("Vælg uge (mandag)", value=_monday(today))
    week_start = _monday(week_start)
    week_dates = [week_start + _dt.timedelta(days=i) for i in range(7)]
    week_from = _iso(week_dates[0])
    week_to = _iso(week_dates[-1])

    # Recipes for dropdown
    recipes = fetch_recipes()  # [(uid,name)]
    recipe_name_by_uid = {uid: name for uid, name in recipes}
    recipe_uids = [""] + [uid for uid, _ in recipes]

    # Existing plan
    plan_rows = fetch_meal_plan(week_from, week_to)
    plan_by_date = {d: (ruid, title, servings, note) for (d, ruid, title, servings, note) in plan_rows}

    st.caption("Planlæg 7 dage. Vælg en opskrift eller skriv en titel (fx 'Rester').")

    with st.container(border=True):
        for d in week_dates:
            d_str = _iso(d)
            ruid, title, servings, note = plan_by_date.get(d_str, (None, "", 1.0, ""))

            row_cols = st.columns([1.25, 2.4, 1.1, 0.8], vertical_alignment="center")
            with row_cols[0]:
                st.markdown(f"**{d.strftime('%a %d/%m')}**")

            with row_cols[1]:
                current_uid = ruid or ""
                idx = recipe_uids.index(current_uid) if current_uid in recipe_uids else 0
                chosen_uid = st.selectbox(
                    "Opskrift",
                    options=recipe_uids,
                    format_func=lambda u: ("— vælg opskrift —" if u == "" else recipe_name_by_uid.get(u, u)),
                    index=idx,
                    key=f"mp_recipe_{d_str}",
                    label_visibility="collapsed",
                )

            with row_cols[2]:
                st.text_input(
                    "Titel",
                    value=(title or ""),
                    key=f"mp_title_{d_str}",
                    label_visibility="collapsed",
                    placeholder="fx Rester…",
                )

            with row_cols[3]:
                st.text_input(
                    "Antal",
                    value=str(int(servings)) if float(servings).is_integer() else str(servings),
                    key=f"mp_serv_{d_str}",
                    label_visibility="collapsed",
                    placeholder="1",
                )

            st.text_input(
                f"Note {d_str}",
                value=(note or ""),
                key=f"mp_note_{d_str}",
                label_visibility="collapsed",
                placeholder="Note (valgfri)…",
            )

            bcols = st.columns([1, 1, 6], vertical_alignment="center")
            with bcols[0]:
                if st.button("Gem", key=f"mp_save_{d_str}", type="secondary"):
                    raw = (ss.get(f"mp_serv_{d_str}") or "").strip().replace(",", ".")
                    try:
                        s = float(raw) if raw else 1.0
                    except Exception:
                        s = 1.0
                    s = 1.0 if s <= 0 else s

                    t = (ss.get(f"mp_title_{d_str}") or "").strip()
                    n = (ss.get(f"mp_note_{d_str}") or "").strip()
                    cu = chosen_uid if chosen_uid != "" else None

                    # If no recipe and no title -> clear
                    if cu is None and not t:
                        clear_meal_for_date(d_str)
                    else:
                        # If recipe chosen and no title, auto title = recipe name
                        if cu is not None and not t:
                            t = recipe_name_by_uid.get(cu, "")
                        set_meal_for_date(d_str, cu, t, servings=s, note=n)

                    sync_db()
                    st.rerun()

            with bcols[1]:
                if st.button("Ryd", key=f"mp_clear_{d_str}", type="tertiary"):
                    clear_meal_for_date(d_str)
                    sync_db()
                    st.rerun()

    st.divider()

    # Generate shopping list
    left, right = st.columns([2, 1], vertical_alignment="center")
    with left:
        check_home = st.checkbox("Tjek hjemme først (tilføj kun mangler)", value=True)
    with right:
        if st.button("🛒 Generér indkøbsliste", type="primary", use_container_width=True):
            summary = generate_shopping_from_mealplan(week_from, week_to, check_pantry_first=check_home)
            sync_db()
            st.success(
                f"Tilføjet {summary.get('added',0)} vare(r). "
                f"Samlet: {summary.get('merged_items',0)}. "
                f"Springet over (hjemme-match): {summary.get('skipped_home',0)}."
            )
            st.rerun()

    st.divider()
    st.subheader("📚 Opskriftsbibliotek")

    # Add recipe
    with st.form("add_recipe_form", clear_on_submit=True, border=False):
        c1, c2 = st.columns([3, 1], vertical_alignment="bottom")
        with c1:
            st.text_input(
                "Ny opskrift",
                key="new_recipe_name",
                placeholder="Fx Chili con carne",
                label_visibility="collapsed",
            )
        with c2:
            add_r = st.form_submit_button("Tilføj", icon=":material/add:")

        if add_r:
            name = (ss.get("new_recipe_name") or "").strip()
            if name:
                add_recipe(name)
                sync_db()
                st.rerun()

    # Edit recipes
    recipes = fetch_recipes()
    if not recipes:
        st.info("Ingen opskrifter endnu. Tilføj en øverst.")
    else:
        ruids = [uid for uid, _ in recipes]
        rnames = {uid: n for uid, n in recipes}

        chosen = st.selectbox(
            "Vælg opskrift",
            options=ruids,
            format_func=lambda u: rnames.get(u, u),
            key="recipe_edit_uid",
        )

        a1, a2 = st.columns([1, 3], vertical_alignment="center")
        with a1:
            if st.button("Slet opskrift", type="tertiary", key="delete_recipe_btn"):
                delete_recipe(chosen)
                sync_db()
                st.rerun()
        with a2:
            st.caption("Tilføj ingredienser. ⭐ kan bruges til standardvarer.")

        items = fetch_recipe_items(chosen)

        # Add ingredient
        with st.form("add_recipe_item_form", clear_on_submit=True, border=False):
            c1, c2, c3, c4, c5 = st.columns([2.5, 1, 1.5, 0.7, 1], vertical_alignment="bottom")
            with c1:
                st.text_input(
                    "Ingrediens",
                    key="ri_text",
                    placeholder="Fx hakket oksekød",
                    label_visibility="collapsed",
                )
            with c2:
                st.text_input("Antal", key="ri_qty", placeholder="1", label_visibility="collapsed")
            with c3:
                st.selectbox(
                    "Kategori",
                    ss["shopping_categories"],
                    index=ss["shopping_categories"].index("Ukategoriseret")
                    if "Ukategoriseret" in ss["shopping_categories"]
                    else 0,
                    key="ri_cat",
                    label_visibility="collapsed",
                )
            with c4:
                st.checkbox("⭐", key="ri_std", help="Markér ingrediens som standardvare")
            with c5:
                add_i = st.form_submit_button("Tilføj", icon=":material/add:")

            if add_i:
                text = (ss.get("ri_text") or "").strip()
                if text:
                    raw = (ss.get("ri_qty") or "").strip().replace(",", ".")
                    try:
                        q = float(raw) if raw else 1.0
                    except Exception:
                        q = 1.0
                    q = 1.0 if q <= 0 else q

                    cat = (ss.get("ri_cat") or "Ukategoriseret").strip() or "Ukategoriseret"
                    is_std = 1 if ss.get("ri_std") else 0

                    add_recipe_item(chosen, text, q, cat, is_standard=is_std)
                    if is_std:
                        upsert_standard(text=text, category=cat, default_qty=q)
                    sync_db()
                    st.rerun()

        if not items:
            st.info("Ingen ingredienser endnu.")
        else:
            for item_uid, text, qty, cat, is_std in items:
                with st.container(horizontal=True, vertical_alignment="center"):
                    st.markdown(f"{_fmt_qty(qty)} × {text}  \n:small[{cat}]")

                    star_label = "⭐" if is_std else "☆"
                    if st.button(
                        star_label,
                        key=f"ri_star_{item_uid}",
                        type="tertiary",
                        help="Toggle standardvare",
                    ):
                        new_std = 0 if is_std else 1
                        info = set_recipe_item_standard(item_uid, new_std)
                        if info:
                            t, c, q = info
                            if new_std == 1:
                                upsert_standard(t, c, q)
                            else:
                                delete_standard(t)
                        sync_db()
                        st.rerun()

                    if st.button(":material/delete:", key=f"ri_del_{item_uid}", type="tertiary"):
                        delete_recipe_item(item_uid)
                        sync_db()
                        st.rerun()
