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


# ----- Init -----
if "items" not in state:
    state.items = [
        Item(text="Mælk"),
        Item(text="Æg"),
        Item(text="Kaffe"),
    ]

if "new_item_text" not in state:
    state.new_item_text = ""


# ----- Actions -----
def add_item():
    txt = (state.new_item_text or "").strip()
    if not txt:
        return
    state.items.append(Item(text=txt))
    state.new_item_text = ""


def toggle_bought(i: int):
    state.items[i].bought = not state.items[i].bought


def remove_item(i: int):
    state.items.pop(i)


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

# Liste (kompakt, iPhone-venlig)
if state.items:
    with st.container(gap=None, border=True):
        # Ikke-købte først
        ordered = sorted(
            list(enumerate(state.items)),
            key=lambda x: (x[1].bought, ),  # False før True
        )

        for i, it in ordered:
            with st.container(horizontal=True, vertical_alignment="center"):
                # Tekst (stretch) + streget over hvis købt
                label = f"~~{it.text}~~" if it.bought else it.text
                st.markdown(label)

                # Købt knap (toggle)
                st.button(
                    "Købt" if not it.bought else "Fortryd",
                    type="secondary" if not it.bought else "tertiary",
                    on_click=toggle_bought,
                    args=[i],
                    key=f"bought_{it.uid}",
                )

                # Fjern knap
                st.button(
                    ":material/delete:",
                    type="tertiary",
                    on_click=remove_item,
                    args=[i],
                    key=f"remove_{it.uid}",
                )
else:
    st.info("Listen er tom.")
