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
    # recipes
    add_recipe,
    delete_recipe,
    fetch_recipes,
    fetch_recipe_items,
    delete_recipe_item,
    set_recipe_done,
    recipe_add_or_merge,
    update_recipe_item_qty,
    # meal plan
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
    # Kladder til dropdown (opdateres hver rerun)
    draft_recipes = fetch_recipes(done=0)  # [(uid,name,is_done)]
    draft_options = [""] + [uid for uid, _, _ in draft_recipes]
    draft_name = {uid: name for uid, name, _ in draft_recipes}

    with st.form("add_item_form", border=False, clear_on_submit=True):
        st.text_input("Vare", label_visibility="collapsed", placeholder="Tilføj vare…", key="new_item_text")

        c1, c2, c3 = st.columns([1, 1.2, 1.6], vertical_alignment="bottom")
        with c1:
            st.text_input("Antal", label_visibility="collapsed", placeholder="Antal", key="new_item_qty_text")
        with c2:
            st.selectbox(
                "Kategori",
                ss["shopping_categories"],
                index=ss["shopping_categories"].index("Ukategoriseret"),
                key="new_item_cat",
                label_visibility="collapsed",
            )
        with c3:
            st.selectbox(
                "Tilføj til opskrift (kladde)",
                options=draft_options,
                format_func=lambda u: "— Ingen —" if u == "" else draft_name.get(u, u),
                key="new_item_recipe_uid",
                label_visibility="collapsed",
            )

        c4, c5 = st.columns([1, 2], vertical_alignment="center")
        with c4:
            st.checkbox("⭐", key="new_item_std", help="Markér som standardvare")
        with c5:
            submitted = st.form_submit_button("Tilføj", icon=":material/add:")

        if submitted:
            text = (ss.get("new_item_text") or "").strip()
            if text:
                qty = _parse_qty(ss.get("new_item_qty_text"))
                cat = _clean_cat(ss.get("new_item_cat") or "Ukategoriseret")
                is_std = 1 if ss.get("new_item_std") else 0
                recipe_uid = ss.get("new_item_recipe_uid") or ""

                # 1) til indkøbslisten
                add_shopping(text=text, qty=qty, category=cat, is_standard=is_std)

                # 2) til opskrift (kladde) med samme kategori
                if recipe_uid:
                    recipe_add_or_merge(recipe_uid, text, qty, cat, is_standard=is_std)

                # 3) standard
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

    # Standardvarer box (valgfrit at have her - beholdt simpelt)
    standards = fetch_standards()
    shopping_rows_now = fetch_shopping()
    pantry_textkeys = {t.strip().lower() for (_, t, _, _, _) in pantry_rows} if pantry_rows else set()
    shopping_textkeys = {t.strip().lower() for (_, t, _, _, _) in shopping_rows_now} if shopping_rows_now else set()

    if standards:
        missing = []
        for text, cat, default_qty in standards:
            k = (text or "").strip().lower()
            in_home = k in pantry_textkeys
            in_shop = k in shopping_textkeys
            if not in_home and not in_shop:
                missing.append((text, cat, default_qty, k))

        if missing:
            st.divider()
            with st.container(border=True):
                st.subheader("⭐ Standardvarer • Mangler")
                for text, cat, default_qty, k in missing:
                    left, right = st.columns([4, 1], vertical_alignment="center")
                    with left:
                        st.markdown(f"**{text}**  \n:small[{cat}]")
                    with right:
                        if st.button("Tilføj", key=f"std_add_missing_{k}", width="content"):
                            add_shopping(text=text, qty=default_qty, category=cat, is_standard=1)
                            sync_db()
                            st.rerun()

# -----------------------------
# TAB: Ugemenu (kun færdige opskrifter)
# -----------------------------
with tab_menu:
    st.subheader("📅 Ugemenu")

    today = _dt.date.today()
    week_start = st.date_input("Vælg uge (mandag)", value=_monday(today), key="menu_week_start_input")
    week_start = _monday(week_start)
    week_dates = [week_start + _dt.timedelta(days=i) for i in range(7)]
    week_from = _iso(week_dates[0])
    week_to = _iso(week_dates[-1])

    done_recipes = fetch_recipes(done=1)  # (uid,name,is_done)
    recipe_name_by_uid = {uid: name for uid, name, _ in done_recipes}
    recipe_uids = [""] + [uid for uid, _, _ in done_recipes]

    plan_rows = fetch_meal_plan(week_from, week_to)
    plan_by_date = {d: (ruid, title, servings, note) for (d, ruid, title, servings, note) in plan_rows}

    st.caption("Ugemenu bruger kun **færdige opskrifter**.")

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
                    format_func=lambda u: "— vælg opskrift —" if u == "" else recipe_name_by_uid.get(u, u),
                    index=idx,
                    key=f"mp_recipe_{d_str}",
                    label_visibility="collapsed",
                )
            with row_cols[2]:
                st.text_input("Titel", value=(title or ""), key=f"mp_title_{d_str}", label_visibility="collapsed", placeholder="(valgfri)")
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
# TAB: Opskrifter (kladder + færdige)
# -----------------------------
with tab_recipes:
    st.subheader("📚 Opskrifter")

    tab_drafts, tab_done = st.tabs(["📝 Ikke færdige", "✅ Færdige"])

    # -----------------------------
    # Drafts
    # -----------------------------
    with tab_drafts:
        st.caption("Tilføj ingredienser ved at vælge en kladde i dropdown når du tilføjer varer til indkøbslisten.")

        with st.form("new_recipe_form", border=False, clear_on_submit=True):
            c1, c2 = st.columns([3, 1], vertical_alignment="bottom")
            with c1:
                st.text_input("Ny opskrift (kladde)", key="new_recipe_name", placeholder="Fx Lasagne", label_visibility="collapsed")
            with c2:
                add_btn = st.form_submit_button("Opret", icon=":material/add:")
            if add_btn:
                name = (ss.get("new_recipe_name") or "").strip()
                if name:
                    add_recipe(name, is_done=0)
                    sync_db()
                    st.rerun()

        drafts = fetch_recipes(done=0)  # (uid,name,is_done)
        if not drafts:
            st.info("Ingen kladder endnu.")
        else:
            ruids = [uid for uid, _, _ in drafts]
            rnames = {uid: name for uid, name, _ in drafts}
            chosen = st.selectbox("Vælg kladde", options=ruids, format_func=lambda u: rnames.get(u, u), key="draft_choice")

            items = fetch_recipe_items(chosen)  # (uid,text,qty,cat,is_std)

            a1, a2, a3 = st.columns([1, 1, 3], vertical_alignment="center")
            with a1:
                if st.button("Slet kladde", type="tertiary", key="delete_draft_btn", width="content"):
                    delete_recipe(chosen)
                    sync_db()
                    st.rerun()
            with a2:
                if st.button("Markér som færdig", type="primary", key="mark_done_btn", width="content"):
                    set_recipe_done(chosen, 1)
                    sync_db()
                    st.rerun()
            with a3:
                st.caption("Her kan du justere mængder (mobilvenligt).")

            if not items:
                st.info("Ingen ingredienser endnu. Tilføj varer på indkøbslisten og vælg denne kladde i dropdown.")
            else:
                for item_uid, text, qty, cat, is_std in items:
                    with st.container(border=True):
                        top = st.columns([3, 1], vertical_alignment="center")
                        with top[0]:
                            st.markdown(f"**{text}**  \n:small[{cat}]")
                        with top[1]:
                            if st.button(":material/delete:", key=f"del_ing_{item_uid}", type="tertiary", width="content"):
                                delete_recipe_item(item_uid)
                                sync_db()
                                st.rerun()

                        new_qty = st.number_input(
                            "Mængde",
                            min_value=0.0,
                            value=float(qty),
                            step=1.0,
                            key=f"qty_{item_uid}",
                            label_visibility="collapsed",
                        )
                        if st.button("Gem mængde", key=f"save_qty_{item_uid}", type="secondary", width="stretch"):
                            update_recipe_item_qty(item_uid, float(new_qty))
                            sync_db()
                            st.rerun()

    # -----------------------------
    # Finished
    # -----------------------------
    with tab_done:
        done = fetch_recipes(done=1)  # (uid,name,is_done)
        if not done:
            st.info("Ingen færdige opskrifter endnu.")
        else:
            ruids = [uid for uid, _, _ in done]
            rnames = {uid: name for uid, name, _ in done}
            chosen = st.selectbox("Vælg færdig opskrift", options=ruids, format_func=lambda u: rnames.get(u, u), key="done_choice")

            items = fetch_recipe_items(chosen)

            a1, a2, a3 = st.columns([1, 1, 3], vertical_alignment="center")
            with a1:
                if st.button("Slet", type="tertiary", key="delete_done_btn", width="content"):
                    delete_recipe(chosen)
                    sync_db()
                    st.rerun()
            with a2:
                if st.button("Gør til kladde", type="secondary", key="mark_draft_btn", width="content"):
                    set_recipe_done(chosen, 0)
                    sync_db()
                    st.rerun()
            with a3:
                st.caption("Færdige opskrifter kan bruges i ugemenuen.")

            if not items:
                st.info("Ingen ingredienser.")
            else:
                for _uid, text, qty, cat, is_std in items:
                    st.markdown(f"- {_fmt_qty(qty)} × **{text}**  :small[{cat}]")
