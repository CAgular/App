# -*- coding: utf-8 -*-
import streamlit as st
from dataclasses import dataclass, field
import uuid

st.set_page_config(page_title="Indkøbsliste", page_icon="🛒")

state = st.session_state


@dataclass
class Item:
    text: str
    bought: bool = False
    uid: uuid.UUID = field(default_factory=uuid.uuid4)


# ----- Init / repair state -----
def ensure_state():
    # Hvis noget andet i app'en har skrevet state.items til noget mærkeligt,
    # så genskab som en ren liste.
    if "items" not in state or state.items is None:
        state.items = []

    # Hvis det ikke er en liste, så prøv at konvertere – ellers reset.
    if not isinstance(state.items, list):
        try:
            state.items = list(state.items)
        except Exception:
            state.items = []

    # Backfill demo-items hvis listen er helt tom første gang
    if len(state.items) == 0 and "items_seeded" not in state:
        state.items = [Item(text="Mælk"), Item(text="Æg"), Item(text="Kaffe")]
        state.items_seeded = True

    if "new_item_text" not in state:
        state.new_item_text = ""


ensure_state()


# ----- Actions -----
def add_item():
    txt = (state.new_item_text or "").strip()
    if not txt:
        return
    state.items.append(Item(text=txt))
    state.new_item_text = ""


def toggle_bought(uid_str: str):
    # Toggle via uid (robust mod reordering)
    for it in state.items:
        if str(it.uid) == uid_str:
            it.bought = not it.bought
            break


def remove_item(uid_str: str):
    state.items = [it for it in state.items if str(it.uid) != uid_str]


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

if state.items:
    with st.container(gap=None, border=True):
        # Vis ikke-købte først (uden sort/enumerate)
        for it in [x for x in state.items if not x.bought]:
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

        for it in [x for x in state.items if x.bought]:
            with st.container(horizontal=True, vertical_alignment="center"):
                st.markdown(f"~~{it.text}~~")
                st.button(
                    "Fortryd",
                    type="tertiary",
                    on_click=toggle_bought,
                    args=[str(it.uid)],
                    key=f"unbought_{it.uid}",
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
