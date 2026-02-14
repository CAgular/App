# -*- coding: utf-8 -*-
import json
import os
import uuid
from dataclasses import dataclass, asdict, field

import streamlit as st

st.set_page_config(page_title="Indkøbsliste", page_icon="🛒")
state = st.session_state

DATA_DIR = "data"
DATA_FILE = os.path.join(DATA_DIR, "shopping_list.json")


@dataclass
class ShoppingItem:
    text: str
    qty: float = 1.0
    category: str = "Ukategoriseret"
    uid: str = field(default_factory=lambda: str(uuid.uuid4()))


# ---------- Storage ----------
def _ensure_storage_dir():
    os.makedirs(DATA_DIR, exist_ok=True)


def load_items() -> list[ShoppingItem]:
    _ensure_storage_dir()
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)

        items: list[ShoppingItem] = []
        for x in raw if isinstance(raw, list) else []:
            if not isinstance(x, dict):
                continue
            txt = (x.get("text") or x.get("name") or "").strip()
            if not txt:
                continue
            cat = (x.get("category") or "Ukategoriseret").strip() or "Ukategoriseret"
            uid = str(x.get("uid") or str(uuid.uuid4()))

            q = x.get("qty", x.get("quantity", 1))
            try:
                q = float(q)
            except Exception:
                q = 1.0
            if q <= 0:
                q = 1.0

            items.append(ShoppingItem(text=txt, qty=q, category=cat, uid=uid))
        return items
    except Exception:
        return []


def save_items(items: list[ShoppingItem]) -> None:
    _ensure_storage_dir()
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump([asdict(it) for it in items], f, ensure_ascii=False, indent=2)


# ---------- Init ----------
def ensure_state():
    if "shopping_items" not in state:
        state["shopping_items"] = load_items()

    if "new_item_text" not in state:
        state["new_item_text"] = ""

    # antal som tekst (for iPhone)
    if "new_item_qty_text" not in state:
        state["new_item_qty_text"] = "1"

    if "new_item_cat" not in state:
        state["new_item_cat"] = "Ukategoriseret"

    if "shopping_categories" not in state:
        state["shopping_categories"] = [
            "Frugt & grønt",
            "Kød & fisk",
            "Mejeri",
            "Brød",
            "Kolonial",
            "Frost",
            "Drikkevarer",
            "Diverse",
            "Ukategoriseret",
        ]


ensure_state()


# ---------- Actions ----------
def _parse_qty(s: str) -> float:
    """
    Tillad: 1, 2, 0.5, 1.5, 1,5
    Tom/ugyldigt -> 1
    <=0 -> 1
    """
    s = (s or "").strip()
    if not s:
        return 1.0
    s = s.replace(",", ".")
    try:
        q = float(s)
    except Exception:
        return 1.0
    return 1.0 if q <= 0 else q


def add_item():
    txt = (state.get("new_item_text") or "").strip()
    if not txt:
        return

    q = _parse_qty(state.get("new_item_qty_text"))
    cat = (state.get("new_item_cat") or "Ukategoriseret").strip() or "Ukategoriseret"

    state["shopping_items"].append(ShoppingItem(text=txt, qty=q, category=cat))
    state["new_item_text"] = ""
    state["new_item_qty_text"] = "1"
    save_items(state["shopping_items"])


def mark_bought(uid: str):
    state["shopping_items"] = [it for it in state["shopping_items"] if it.uid != uid]
    save_items(state["shopping_items"])


def remove_item(uid: str):
    state["shopping_items"] = [it for it in state["shopping_items"] if it.uid != uid]
    save_items(state["shopping_items"])


# ---------- UI ----------
with st.container(horizontal_alignment="center"):
    st.title("🛒 Indkøbsliste", width="content", anchor=False)

with st.form(key="new_item_form", border=False):
    with st.container(horizontal=True, vertical_alignment="bottom"):
        st.text_input(
            "Ny vare",
            label_visibility="collapsed",
            placeholder="Tilføj vare…",
            key="new_item_text",
        )

        # lille tekstfelt til antal
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
            on_click=add_item,
        )

items = state["shopping_items"]

if not items:
    st.info("Listen er tom.")
else:
    # Sortér efter kategori, men vis ikke kategori på linjerne
    def cat_key(cat: str):
        return ("zzzz" if cat == "Ukategoriseret" else cat.lower())

    categories = sorted({(it.category or "Ukategoriseret") for it in items}, key=cat_key)

    with st.container(gap=None, border=True):
        for cat in categories:
            cat_items = [it for it in items if (it.category or "Ukategoriseret") == cat]
            if not cat_items:
                continue

            for it in cat_items:
                with st.container(horizontal=True, vertical_alignment="center"):
                    q = float(it.qty)
                    qty_txt = str(int(q)) if q.is_integer() else str(q)
                    st.markdown(f"{qty_txt} × {it.text}")

                    st.button(
                        "Købt",
                        type="secondary",
                        on_click=mark_bought,
                        args=[it.uid],
                        key=f"b_{it.uid}",
                    )
                    st.button(
                        ":material/delete:",
                        type="tertiary",
                        on_click=remove_item,
                        args=[it.uid],
                        key=f"r_{it.uid}",
                    )
