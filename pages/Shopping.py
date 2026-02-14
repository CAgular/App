# -*- coding: utf-8 -*-
import streamlit as st
from dataclasses import dataclass, field
import uuid

st.set_page_config(page_title="Indkøbsliste", page_icon="🛒")

state = st.session_state


@dataclass
class ShoppingItem:
    text: str
    bought: bool = False
    uid: uuid.UUID = field(default_factory=uuid.uuid4)


# ----- Init / repair state -----
def ensure_state():
    if "shopping_items" not in state or state["shopping_items"] is None:
        state["shopping_items"] = []

    # Sørg for ren liste
    if not isinstance(state["shopping_items"], list):
        try:
            state["shopping_items"] = list(state["shopping_items"])
        except Exception:
            state["shopping_items"] = []

    # Seed kun første gang
    if len(state["shopping_items"]) == 0 and "shopping_seeded" not in state:
        state["shopping_items"] = [
            ShoppingItem(text="Mælk"),
            ShoppingItem(text="Æg"),
            ShoppingItem(text="Kaffe"),
        ]
        state["shopping_seeded"] = True

    if "new_item_text" not in state:
        state["new_item_text"] = ""


ensure_state()


# ----- Actions -----
def add_item():
    txt = (state.get("new_item_text") or "").strip()
    if not txt:
        return
    state["shopping_items"].append(ShoppingItem(text=txt))
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
        st.form_submit_button(
            "Tilføj",
            icon=":material/add:",
            on_click=add_item,
        )

items = state["shopping_items"]

if items:
    with st.container(gap=None, border=True):
        # Ikke-købte først (kompakt, ingen sort/enumerate)
        for it in [x for x in items if not x.bought]:
            with st.container(horizontal=True, vertical_alignment="center"):
                st.markdown(it.text)
                st.button(
                    "Købt",
                    type="secondary",
                    on_click=toggle_bought,
                    args=[str(it.uid)],
                    key=f"bought_{it.uid}",
                )
                st.button(
                    ":material/delete:",
                    type="tertiary",
                    on_click=remove_item,
                    args=[str(it.uid)],
                    key=f"remove_{it.uid}",
                )

        for it in [x for x in items if x.bought]:
            with st.container(horizontal=True, vertical_alignment="center"):
                st.markdown(f"~~{it.text}~~")
                st.button(
                    "Fortryd",
                    type="tertiary",
                    on_click=toggle_bought,
                    args=[str(it.uid)],
                    key=f"undo_{it.uid}",
                )
                st.button(
                    ":material/delete:",
                    type="tertiary",
                    on_click=remove_item,
                    args=[str(it.uid)],
                    key=f"remove2_{it.uid}",
                )
else:
    st.info("Listen er tom.")
