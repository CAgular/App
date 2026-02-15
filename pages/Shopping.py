# -*- coding: utf-8 -*-
import json
import os
import uuid
from dataclasses import dataclass, asdict, field

import streamlit as st

st.set_page_config(page_title="Indkøb", page_icon="🛒")
state = st.session_state

DATA_DIR = "data"
DATA_FILE = os.path.join(DATA_DIR, "shopping_data.json")


# ----------------- Models -----------------
@dataclass
class ShoppingItem:
    text: str
    qty: float = 1.0
    category: str = "Ukategoriseret"  # (din tidligere "indkøbskategori")
    uid: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class PantryItem:
    text: str
    qty: float = 1.0
    location: str = "Ukategoriseret"  # køleskab/fryser/bryggers/...
    uid: str = field(default_factory=lambda: str(uuid.uuid4()))


# ----------------- Helpers -----------------
def _ensure_storage_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def _parse_qty(s) -> float:
    """
    Tillad: 1, 2, 0.5, 1.5, 1,5
    Tom/ugyldigt -> 1
    <=0 -> 1
    """
    if s is None:
        return 1.0
    s = str(s).strip()
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


def load_data():
    _ensure_storage_dir()
    if not os.path.exists(DATA_FILE):
        return {"shopping": [], "pantry": [], "pantry_location_memory": {}}

    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f) or {}
    except Exception:
        return {"shopping": [], "pantry": [], "pantry_location_memory": {}}

    # robust defaults
    raw.setdefault("shopping", [])
    raw.setdefault("pantry", [])
    raw.setdefault("pantry_location_memory", {})

    # normalize arrays
    if not isinstance(raw["shopping"], list):
        raw["shopping"] = []
    if not isinstance(raw["pantry"], list):
        raw["pantry"] = []
    if not isinstance(raw["pantry_location_memory"], dict):
        raw["pantry_location_memory"] = {}

    return raw


def save_data():
    _ensure_storage_dir()
    out = {
        "shopping": [asdict(x) for x in state["shopping_items"]],
        "pantry": [asdict(x) for x in state["pantry_items"]],
        "pantry_location_memory": state["pantry_location_memory"],
    }
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)


def ensure_state():
    if "data_loaded" in state:
        return

    raw = load_data()

    # migrate shopping
    shopping_items = []
    for x in raw["shopping"]:
        if not isinstance(x, dict):
            continue
        txt = (x.get("text") or x.get("name") or "").strip()
        if not txt:
            continue
        shopping_items.append(
            ShoppingItem(
                text=txt,
                qty=_parse_qty(x.get("qty", 1)),
                category=(x.get("category") or "Ukategoriseret").strip() or "Ukategoriseret",
                uid=str(x.get("uid") or str(uuid.uuid4())),
            )
        )

    # migrate pantry
    pantry_items = []
    for x in raw["pantry"]:
        if not isinstance(x, dict):
            continue
        txt = (x.get("text") or x.get("name") or "").strip()
        if not txt:
            continue
        pantry_items.append(
            PantryItem(
                text=txt,
                qty=_parse_qty(x.get("qty", 1)),
                location=(x.get("location") or "Ukategoriseret").strip() or "Ukategoriseret",
                uid=str(x.get("uid") or str(uuid.uuid4())),
            )
        )

    state["shopping_items"] = shopping_items
    state["pantry_items"] = pantry_items
    state["pantry_location_memory"] = raw.get("pantry_location_memory", {}) or {}

    # inputs
    state.setdefault("new_item_text", "")
    state.setdefault("new_item_qty_text", "1")
    state.setdefault("new_item_cat", "Ukategoriseret")

    # pantry prompt state
    state.setdefault("pantry_prompt_uid", None)
    state.setdefault("pantry_prompt_qty_text", "1")

    # dropdowns
    state.setdefault(
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
    state.setdefault(
        "pantry_locations",
        [
            "Køleskab",
            "Fryser",
            "Bryggers",
            "Skab",
            "Badeværelse",
            "Kælder",
            "Garage",
            "Ukategoriseret",
        ],
    )

    state["data_loaded"] = True


ensure_state()


# ----------------- Core logic -----------------
def add_to_shopping(text: str, qty: float, category: str):
    text = (text or "").strip()
    if not text:
        return
    if qty <= 0:
        qty = 1.0
    category = (category or "Ukategoriseret").strip() or "Ukategoriseret"

    state["shopping_items"].append(ShoppingItem(text=text, qty=qty, category=category))
    save_data()


def add_to_pantry(text: str, qty: float):
    """
    When bought -> add to pantry.
    Location is remembered per item name (first time user sets it).
    If already exists in pantry with same text+location -> increase qty.
    """
    text = (text or "").strip()
    if not text:
        return
    if qty <= 0:
        qty = 1.0

    mem = state["pantry_location_memory"]
    location = (mem.get(text.lower()) or "Ukategoriseret").strip() or "Ukategoriseret"

    # merge if existing same item+location
    for it in state["pantry_items"]:
        if it.text.strip().lower() == text.lower() and it.location == location:
            it.qty = float(it.qty) + float(qty)
            save_data()
            return

    state["pantry_items"].append(PantryItem(text=text, qty=qty, location=location))
    save_data()


def shopping_add_item():
    txt = (state.get("new_item_text") or "").strip()
    if not txt:
        return
    qty = _parse_qty(state.get("new_item_qty_text"))
    cat = (state.get("new_item_cat") or "Ukategoriseret").strip() or "Ukategoriseret"

    add_to_shopping(txt, qty, cat)
    state["new_item_text"] = ""
    state["new_item_qty_text"] = "1"


def shopping_mark_bought(uid: str):
    # find item
    item = None
    for it in state["shopping_items"]:
        if it.uid == uid:
            item = it
            break
    if not item:
        return

    # remove from shopping
    state["shopping_items"] = [x for x in state["shopping_items"] if x.uid != uid]

    # add to pantry (auto)
    add_to_pantry(item.text, float(item.qty))

    save_data()


def shopping_remove(uid: str):
    state["shopping_items"] = [x for x in state["shopping_items"] if x.uid != uid]
    save_data()


def pantry_set_location(uid: str, new_loc: str):
    new_loc = (new_loc or "Ukategoriseret").strip() or "Ukategoriseret"
    for it in state["pantry_items"]:
        if it.uid == uid:
            it.location = new_loc
            # remember per name
            state["pantry_location_memory"][it.text.lower()] = new_loc
            break
    save_data()


def pantry_used(uid: str):
    # open prompt
    state["pantry_prompt_uid"] = uid
    state["pantry_prompt_qty_text"] = "1"


def pantry_prompt_cancel():
    state["pantry_prompt_uid"] = None


def pantry_prompt_confirm_add_back():
    uid = state.get("pantry_prompt_uid")
    qty_used = _parse_qty(state.get("pantry_prompt_qty_text"))

    # find pantry item
    p = None
    for it in state["pantry_items"]:
        if it.uid == uid:
            p = it
            break
    if not p:
        state["pantry_prompt_uid"] = None
        return

    # Add back to shopping
    add_to_shopping(p.text, qty_used, "Ukategoriseret")

    # Decrease pantry qty / remove if empty
    remaining = float(p.qty) - float(qty_used)
    if remaining > 0:
        p.qty = remaining
    else:
        state["pantry_items"] = [x for x in state["pantry_items"] if x.uid != uid]

    save_data()
    state["pantry_prompt_uid"] = None


# ----------------- UI -----------------
with st.container(horizontal_alignment="center"):
    st.title("🛒 Indkøb", width="content", anchor=False)

tab_shop, tab_pantry = st.tabs(["Indkøbsliste", "Hjemme"])

# --------- TAB: Shopping ----------
with tab_shop:
    with st.form(key="new_item_form", border=False):
        with st.container(horizontal=True, vertical_alignment="bottom"):
            st.text_input(
                "Ny vare",
                label_visibility="collapsed",
                placeholder="Tilføj vare…",
                key="new_item_text",
            )
            st.text_input(
                "Antal",
                label_visibility="collapsed",
                placeholder="Antal",
                key="new_item_qty_text",
            )
            st.selectbox(
                "Kategori",
                options=state["shopping_categories"],
                key="new_item_cat",
                label_visibility="collapsed",
            )
            st.form_submit_button(
                "Tilføj",
                icon=":material/add:",
                on_click=shopping_add_item,
            )

    shopping_items = state["shopping_items"]

    if not shopping_items:
        st.info("Listen er tom.")
    else:
        # sort by category, but don't show category on each line
        def cat_key(cat: str):
            return ("zzzz" if cat == "Ukategoriseret" else cat.lower())

        cats = sorted({(it.category or "Ukategoriseret") for it in shopping_items}, key=cat_key)

        with st.container(gap=None, border=True):
            for cat in cats:
                group = [it for it in shopping_items if (it.category or "Ukategoriseret") == cat]
                if not group:
                    continue

                # bevidst: ingen synlig kategori-overskrift

                for it in group:
                    with st.container(horizontal=True, vertical_alignment="center"):
                        st.markdown(f"{_fmt_qty(it.qty)} × {it.text}")
                        st.button(
                            "Købt",
                            type="secondary",
                            on_click=shopping_mark_bought,
                            args=[it.uid],
                            key=f"shop_b_{it.uid}",
                        )
                        st.button(
                            ":material/delete:",
                            type="tertiary",
                            on_click=shopping_remove,
                            args=[it.uid],
                            key=f"shop_r_{it.uid}",
                        )

# --------- TAB: Pantry ----------
with tab_pantry:
    pantry_items = state["pantry_items"]

    # Prompt area (mini "dialog" uden at kræve ny Streamlit-version)
    prompt_uid = state.get("pantry_prompt_uid")
    if prompt_uid:
        p = next((x for x in pantry_items if x.uid == prompt_uid), None)
        if p:
            with st.container(border=True):
                st.markdown(f"**Tilføj `{p.text}` til indkøbslisten igen?**")
                c1, c2, c3 = st.columns([0.5, 0.25, 0.25], gap="small")
                with c1:
                    st.text_input(
                        "Antal",
                        label_visibility="collapsed",
                        placeholder="Antal",
                        key="pantry_prompt_qty_text",
                    )
                with c2:
                    st.button("Ja", type="primary", on_click=pantry_prompt_confirm_add_back)
                with c3:
                    st.button("Nej", type="tertiary", on_click=pantry_prompt_cancel)

    if not pantry_items:
        st.info("Ingen varer registreret derhjemme endnu.")
    else:
        # sort by location, but keep UI minimal
        def loc_key(loc: str):
            return ("zzzz" if loc == "Ukategoriseret" else loc.lower())

        locs = sorted({(it.location or "Ukategoriseret") for it in pantry_items}, key=loc_key)

        with st.container(gap=None, border=True):
            for loc in locs:
                group = [it for it in pantry_items if (it.location or "Ukategoriseret") == loc]
                if not group:
                    continue

                # du kan vælge at skjule overskriften helt; men her giver den mening i "Hjemme"
                st.caption(loc)

                for it in group:
                    with st.container(horizontal=True, vertical_alignment="center"):
                        st.markdown(f"{_fmt_qty(it.qty)} × {it.text}")

                        # placering vælges (og huskes pr varenavn)
                        st.selectbox(
                            "Placering",
                            options=state["pantry_locations"],
                            index=state["pantry_locations"].index(it.location)
                            if it.location in state["pantry_locations"]
                            else state["pantry_locations"].index("Ukategoriseret"),
                            label_visibility="collapsed",
                            key=f"loc_{it.uid}",
                            on_change=pantry_set_location,
                            args=[it.uid, state.get(f"loc_{it.uid}")],
                        )

                        st.button(
                            "Brugt",
                            type="secondary",
                            on_click=pantry_used,
                            args=[it.uid],
                            key=f"used_{it.uid}",
                        )
