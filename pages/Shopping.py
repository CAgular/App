# -*- coding: utf-8 -*-
import streamlit as st
from dataclasses import dataclass, field
import uuid

st.set_page_config(page_title="Indkøbsliste", page_icon="🛒")
state = st.session_state


@dataclass
class ShoppingItem:
    text: str
    category: str = ""   # tom = "Ukategoriseret"
    bought: bool = False
    uid: uuid.UUID = field(default_factory=uuid.uuid4)


# ----- Init / repair state -----
def ensure_state():
    if "shopping_items" not in state or state["shopping_items"] is None:
        state["shopping_items"] = []

    if not isinstance(state["shopping_items"], list):
        try:
            state["shopping_items"] = list(state["shopping_items"])
        except Exception:
            state["shopping_items"] = []

    if "new_item_text" not in state:
        state["new_item_text"] = ""

    if "new_item_cat" not in state:
        state["new_item_cat"] = "Ukategoriseret"

    # Kendte kategorier (bruges til dropdown + sortering)
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


# ----- Actions -----
def add_item():
    txt = (state.get("new_item_text") or "").strip()
    if not txt:
        return

    cat = (state.get("new_item_cat") or "").strip()
    if not cat:
        cat = "Ukategoriseret"

    state["shopping_items"].append(ShoppingItem(text=txt, category=cat))
    state["new_item_text"] = ""


def toggle_bought(uid_str: str):
    for it in state["shopping_items"]:
        if str(it.uid) == uid_str:
            it.bought = not it.bought
            break


def remove_item(uid_str: str):
    state["shopping_items"] = [
        it for it in state["shopping_items"] if str(it.uid) != uid_str
    ]


# ----- UI -----
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
    # Gruppér efter kategori, uden at vise kategori på varen
    # Sortering: kategori alfabetisk, men "Ukategoriseret" altid sidst
    def cat_key(cat: str):
        return ("zzzz" if cat == "Ukategoriseret" else cat.lower())

    categories = sorted({(it.category or "Ukategoriseret") for it in items}, key=cat_key)

    with st.container(gap=None, border=True):
        for cat in categories:
            cat_items = [it for it in items if (it.category or "Ukategoriseret") == cat]
            if not cat_items:
                continue

            # Lille gruppe-overskrift (kun her ses kategorien)
            st.caption(cat)

            # Ikke-købte først, derefter købte
            for it in [x for x in cat_items if not x.bought]:
                with st.container(horizontal=True, vertical_alignment="center"):
                    st.markdown(it.text)
                    st.button(
                        "Købt",
                        type="secondary",
                        on_click=toggle_bought,
                        args=[str(it.uid)],
                        key=f"b_{it.uid}",
                    )
                    st.button(
                        ":material/delete:",
                        type="tertiary",
                        on_click=remove_item,
                        args=[str(it.uid)],
                        key=f"r_{it.uid}",
                    )

            for it in [x for x in cat_items if x.bought]:
                with st.container(horizontal=True, vertical_alignment="center"):
                    st.markdown(f"~~{it.text}~~")
                    st.button(
                        "Fortryd",
                        type="tertiary",
                        on_click=toggle_bought,
                        args=[str(it.uid)],
                        key=f"u_{it.uid}",
                    )
                    st.button(
                        ":material/delete:",
                        type="tertiary",
                        on_click=remove_item,
                        args=[str(it.uid)],
                        key=f"r2_{it.uid}",
                    )
