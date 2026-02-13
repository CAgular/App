import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import streamlit as st
from src.config import APP_TITLE

# =========================================================
# Page config + nav
# =========================================================
st.set_page_config(page_title=f"{APP_TITLE} • Shopping", page_icon="🛒", layout="centered")
st.link_button("⬅️ Tilbage til forside", "/")
st.title("🛒 Shopping")

# =========================================================
# Style: compact, iPhone-friendly, "quiet" UI
# =========================================================
st.markdown(
    """
    <style>
      .block-container { padding-top: 0.6rem; padding-bottom: 1.1rem; max-width: 820px; }
      div[data-testid="stVerticalBlock"] { gap: 0.30rem; }

      /* Tight headings */
      h2 { margin-top: 0.3rem; }
      h3 { margin-top: 0.45rem; margin-bottom: 0.12rem; }
      h4 { margin-top: 0.35rem; margin-bottom: 0.10rem; }

      /* Rounded inputs */
      div[data-testid="stTextInput"] input,
      div[data-testid="stNumberInput"] input,
      div[data-testid="stSelectbox"] div {
        border-radius: 14px !important;
      }

      /* Buttons (no full-width by default) */
      .stButton>button {
        width: auto;
        padding: 0.46rem 0.62rem;
        border-radius: 14px;
        font-weight: 650;
      }

      /* Tiny icon button */
      .btn-icon .stButton>button{
        width: 40px;
        min-width: 40px;
        height: 36px;
        padding: 0;
        border-radius: 12px;
        font-weight: 850;
      }

      /* Chips */
      .chiprow { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 0.1rem; }
      .chiprow .stButton>button{
        padding: 0.28rem 0.55rem;
        border-radius: 999px;
        font-weight: 700;
      }

      /* Compact list row */
      .row {
        border: 1px solid rgba(49, 51, 63, 0.14);
        border-radius: 14px;
        padding: 0.28rem 0.50rem;
        margin: 0.10rem 0;
        background: rgba(255,255,255,0.02);
      }
      .name {
        font-weight: 760;
        font-size: 1.00rem;
        line-height: 1.10;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
      }
      .qty {
        opacity: 0.78;
        font-weight: 850;
        font-size: 0.92rem;
        white-space: nowrap;
        text-align: right;
      }

      /* Make checkbox slightly smaller */
      div[data-testid="stCheckbox"] input[type="checkbox"]{
        transform: scale(0.90);
        transform-origin: left center;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

# =========================================================
# Persistence
# =========================================================
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
DATA_FILE = DATA_DIR / "shopping_streamlined_v1.json"

DEFAULT_STORES = ["Netto", "Rema 1000", "Føtex", "Lidl", "Apotek", "Bauhaus"]
DEFAULT_CATEGORIES = [
    "Frugt & grønt", "Pålæg", "Mejeri", "Kød", "Fisk", "Brød",
    "Kolonial", "Frost", "Drikke", "Baby", "Husholdning", "Rengøring",
    "Toilet", "DIY", "Andet",
]
DEFAULT_HOME_LOCATIONS = ["Køleskab", "Fryser", "Skab", "Kælder", "Badeværelse", "Andet"]


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def human_time(iso_str: Optional[str]) -> str:
    if not iso_str:
        return "—"
    try:
        dt = datetime.fromisoformat(iso_str)
        return dt.strftime("%d-%m-%Y %H:%M")
    except Exception:
        return iso_str


def load_data() -> Dict:
    if DATA_FILE.exists():
        try:
            return json.loads(DATA_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_data(payload: Dict) -> None:
    DATA_FILE.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def ensure_ids(items: List[Dict]) -> List[Dict]:
    out = []
    for it in items:
        d = dict(it)
        d.setdefault("id", str(uuid.uuid4()))
        out.append(d)
    return out


def norm(s: str) -> str:
    return (s or "").strip()


def key(s: str) -> str:
    return norm(s).lower()


def ensure_state():
    if "shop_v1" in st.session_state:
        return

    data = load_data() or {}
    settings = data.get("settings", {}) if isinstance(data.get("settings", {}), dict) else {}

    st.session_state.shop_v1 = {
        "shopping_items": ensure_ids(data.get("shopping_items", [])),  # includes open/bought
        "standard_items": ensure_ids(data.get("standard_items", [])),
        "home_items": ensure_ids(data.get("home_items", [])),
        "memory": data.get("memory", {}),  # name->(category, store, qty, standard)
        "categories": data.get("categories", DEFAULT_CATEGORIES),
        "stores": data.get("stores", DEFAULT_STORES),
        "home_locations": data.get("home_locations", DEFAULT_HOME_LOCATIONS),
        "settings": {
            "default_store": settings.get("default_store", "Netto"),
            "default_home_location": settings.get("default_home_location", "Køleskab"),
            "show_bought": settings.get("show_bought", False),
        },
        "meta": data.get("meta", {"last_saved": None}),
    }


def persist():
    S = st.session_state.shop_v1
    payload = {
        "shopping_items": S["shopping_items"],
        "standard_items": S["standard_items"],
        "home_items": S["home_items"],
        "memory": S["memory"],
        "categories": S["categories"],
        "stores": S["stores"],
        "home_locations": S["home_locations"],
        "settings": S["settings"],
        "meta": {"last_saved": now_iso()},
    }
    save_data(payload)
    S["meta"]["last_saved"] = payload["meta"]["last_saved"]


ensure_state()
S = st.session_state.shop_v1


# =========================================================
# Memory + suggestions
# =========================================================
def upsert_memory(item_name: str, category: str, store: str, qty: int, is_standard: bool):
    kk = key(item_name)
    if not kk:
        return
    S["memory"][kk] = {
        "name": norm(item_name),
        "category": norm(category),
        "store": norm(store),
        "default_qty": int(qty),
        "is_standard": bool(is_standard),
        "updated_at": now_iso(),
    }
    persist()


def memory_suggestions(prefix: str, limit: int = 8) -> List[Dict]:
    p = key(prefix)
    if not p:
        return []
    hits = []
    for v in S["memory"].values():
        nm = (v.get("name") or "").strip()
        if nm.lower().startswith(p):
            hits.append(v)
    hits.sort(key=lambda x: (len(x.get("name", "")), x.get("updated_at", "")))
    return hits[:limit]


def top_values(values: List[str], n: int = 8) -> List[str]:
    # take order as "priority", keep unique
    out = []
    for v in values:
        v = norm(v)
        if v and v not in out:
            out.append(v)
        if len(out) >= n:
            break
    return out


def match_values(prefix: str, values: List[str], limit: int = 8) -> List[str]:
    p = key(prefix)
    if not p:
        return top_values(values, n=limit)
    matches = [v for v in values if key(v).startswith(p)]
    # fallback contains match
    if len(matches) < limit:
        matches += [v for v in values if p in key(v) and v not in matches]
    return top_values(matches, n=limit)


# =========================================================
# Data ops
# =========================================================
def add_or_merge_shopping(name: str, qty: int, category: str, store: str):
    name, category, store = norm(name), norm(category), norm(store)
    if not name:
        return
    qty = max(1, int(qty))

    for it in S["shopping_items"]:
        if (
            it.get("status") == "open"
            and key(it.get("name", "")) == key(name)
            and norm(it.get("category", "")) == category
            and norm(it.get("store", "")) == store
        ):
            it["qty"] = int(it.get("qty", 1)) + qty
            persist()
            return

    S["shopping_items"].append(
        {
            "id": str(uuid.uuid4()),
            "name": name,
            "qty": qty,
            "category": category or "Andet",
            "store": store or S["settings"].get("default_store", "Netto"),
            "status": "open",
            "created_at": now_iso(),
            "bought_at": None,
        }
    )
    persist()


def add_or_update_standard(name: str, qty: int, category: str, store: str):
    name, category, store = norm(name), norm(category), norm(store)
    if not name:
        return
    qty = max(1, int(qty))

    for it in S["standard_items"]:
        if key(it.get("name", "")) == key(name) and norm(it.get("category", "")) == category and norm(it.get("store", "")) == store:
            it["default_qty"] = qty
            persist()
            return

    S["standard_items"].append(
        {"id": str(uuid.uuid4()), "name": name, "default_qty": qty, "category": category or "Andet", "store": store or S["settings"].get("default_store", "Netto")}
    )
    persist()


def add_to_home(name: str, qty: int, location: str, category: str, store: str):
    name, location = norm(name), norm(location)
    if not name:
        return
    qty = max(1, int(qty))
    for h in S["home_items"]:
        if key(h.get("name", "")) == key(name) and norm(h.get("location", "")) == location:
            h["qty"] = int(h.get("qty", 1)) + qty
            h["category"] = norm(category)
            h["store"] = norm(store)
            h["added_at"] = now_iso()
            persist()
            return

    S["home_items"].append(
        {
            "id": str(uuid.uuid4()),
            "name": name,
            "qty": qty,
            "location": location or S["settings"].get("default_home_location", "Køleskab"),
            "category": norm(category) or "Andet",
            "store": norm(store) or S["settings"].get("default_store", "Netto"),
            "added_at": now_iso(),
            "last_used_at": None,
        }
    )
    persist()


def mark_bought(item_id: str):
    default_loc = S["settings"].get("default_home_location", "Køleskab")
    for it in S["shopping_items"]:
        if it.get("id") == item_id and it.get("status") == "open":
            it["status"] = "bought"
            it["bought_at"] = now_iso()
            persist()
            add_to_home(it.get("name", ""), int(it.get("qty", 1)), default_loc, it.get("category", "Andet"), it.get("store", S["settings"].get("default_store", "Netto")))
            return


def delete_item(item_id: str):
    S["shopping_items"] = [x for x in S["shopping_items"] if x.get("id") != item_id]
    persist()


# =========================================================
# UI helpers
# =========================================================
def chip_row(values: List[str], set_key: str, prefix: str, label: str):
    matches = match_values(prefix, values, limit=8)
    if not matches:
        return
    st.markdown('<div class="chiprow">', unsafe_allow_html=True)
    cols = st.columns(min(4, len(matches)))
    # render as grid of buttons
    for i, v in enumerate(matches[:8]):
        with cols[i % len(cols)]:
            if st.button(v, key=f"{label}_chip_{set_key}_{i}_{v}"):
                st.session_state[set_key] = v
                st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)


# =========================================================
# Keys for add form
# =========================================================
K_NAME = "q_name"
K_QTY = "q_qty"
K_CAT = "q_cat"
K_STORE = "q_store"
K_STD = "q_std"
K_RESET = "q_reset"

st.session_state.setdefault(K_NAME, "")
st.session_state.setdefault(K_QTY, 1)
st.session_state.setdefault(K_CAT, "")
st.session_state.setdefault(K_STORE, "")
st.session_state.setdefault(K_STD, False)
st.session_state.setdefault(K_RESET, False)


def reset_quick_add():
    st.session_state[K_NAME] = ""
    st.session_state[K_QTY] = 1
    st.session_state[K_CAT] = ""
    st.session_state[K_STORE] = ""
    st.session_state[K_STD] = False
    st.session_state[K_RESET] = False


def maybe_prefill_from_memory(current_name: str):
    m = S["memory"].get(key(current_name))
    if not m:
        return
    # only prefill empty fields
    if not norm(st.session_state.get(K_CAT, "")):
        st.session_state[K_CAT] = m.get("category", "")
    if not norm(st.session_state.get(K_STORE, "")):
        st.session_state[K_STORE] = m.get("store", "")
    if int(st.session_state.get(K_QTY, 1) or 1) == 1:
        st.session_state[K_QTY] = int(m.get("default_qty", 1) or 1)
    st.session_state[K_STD] = bool(m.get("is_standard", False))


# =========================================================
# Tabs
# =========================================================
tab_shop, tab_home, tab_std, tab_settings = st.tabs(["🧾 Indkøb", "🏠 Hjemme", "⭐ Standard", "⚙️ Indstillinger"])


# =========================================================
# 🧾 SHOPPING TAB
# =========================================================
with tab_shop:
    # Quick add (no dropdowns by default)
    if st.session_state.get(K_RESET, False):
        reset_quick_add()

    # Prefill as user types
    if norm(st.session_state.get(K_NAME, "")):
        maybe_prefill_from_memory(st.session_state[K_NAME])

    with st.form("quick_add", clear_on_submit=False):
        cA, cB = st.columns([3, 1], vertical_alignment="center")
        with cA:
            st.text_input("Vare", key=K_NAME, placeholder="Skriv fx: bananer")
        with cB:
            st.number_input("Antal", min_value=1, step=1, key=K_QTY)

        cC, cD = st.columns([1, 1], vertical_alignment="center")
        with cC:
            st.text_input("Kategori", key=K_CAT, placeholder="fx Frugt & grønt")
        with cD:
            st.text_input("Butik", key=K_STORE, placeholder=f"fx {S['settings'].get('default_store','Netto')}")

        st.checkbox("Standardvare", key=K_STD)

        add = st.form_submit_button("Tilføj")

    # Suggestions for item name (one-tap)
    nm = norm(st.session_state.get(K_NAME, ""))
    sug = memory_suggestions(nm, limit=8) if nm else []
    if sug:
        cols = st.columns(min(4, len(sug)))
        for i, s in enumerate(sug):
            with cols[i % len(cols)]:
                if st.button(s.get("name", ""), key=f"pick_sug_{i}_{s.get('name','')}"):
                    st.session_state[K_NAME] = s.get("name", "")
                    st.session_state[K_QTY] = int(s.get("default_qty", 1) or 1)
                    st.session_state[K_CAT] = s.get("category", "")
                    st.session_state[K_STORE] = s.get("store", "")
                    st.session_state[K_STD] = bool(s.get("is_standard", False))
                    st.rerun()

    # Chips for category/store
    chip_row(S["categories"], K_CAT, st.session_state.get(K_CAT, ""), "cat")
    chip_row(S["stores"], K_STORE, st.session_state.get(K_STORE, ""), "store")

    # Handle add
    if add:
        name = norm(st.session_state.get(K_NAME, ""))
        qty = int(st.session_state.get(K_QTY, 1) or 1)
        category = norm(st.session_state.get(K_CAT, "")) or "Andet"
        store = norm(st.session_state.get(K_STORE, "")) or S["settings"].get("default_store", "Netto")
        is_std = bool(st.session_state.get(K_STD, False))

        # ensure lists learn new values typed
        if category and category not in S["categories"]:
            S["categories"].insert(0, category)
        if store and store not in S["stores"]:
            S["stores"].insert(0, store)
        persist()

        if not name:
            st.warning("Skriv et varenavn.")
        else:
            add_or_merge_shopping(name, qty, category, store)
            upsert_memory(name, category, store, qty, is_std)
            if is_std:
                add_or_update_standard(name, qty, category, store)

            st.session_state[K_RESET] = True
            st.rerun()

    # List
    show_bought = bool(S["settings"].get("show_bought", False))
    open_items = [x for x in S["shopping_items"] if x.get("status") == "open"]
    bought_items = [x for x in S["shopping_items"] if x.get("status") == "bought"]

    # Grouping: store -> category -> name
    open_items.sort(key=lambda x: (norm(x.get("store", "")), norm(x.get("category", "")), norm(x.get("name", "")).lower()))
    bought_items.sort(key=lambda x: (x.get("bought_at") or ""), reverse=True)

    st.subheader("Indkøbsliste")

    if not open_items:
        st.info("Tom.")
    else:
        to_buy: List[str] = []
        last_group: Tuple[str, str] = ("", "")

        for it in open_items:
            store = norm(it.get("store", "")) or S["settings"].get("default_store", "Netto")
            cat = norm(it.get("category", "")) or "Andet"

            if (store, cat) != last_group:
                st.markdown(f"#### {store} · {cat}")
                last_group = (store, cat)

            st.markdown('<div class="row">', unsafe_allow_html=True)

            c_cb, c_name, c_qty, c_del = st.columns([0.7, 6.9, 1.1, 1.0], vertical_alignment="center")

            cb_key = f"cb_{it['id']}"
            st.session_state.setdefault(cb_key, False)

            with c_cb:
                checked = st.checkbox("købt", key=cb_key, label_visibility="collapsed")
                if checked:
                    to_buy.append(it["id"])

            with c_name:
                st.markdown(f'<div class="name">{it.get("name","")}</div>', unsafe_allow_html=True)

            with c_qty:
                st.markdown(f'<div class="qty">×{int(it.get("qty",1))}</div>', unsafe_allow_html=True)

            with c_del:
                st.markdown('<div class="btn-icon">', unsafe_allow_html=True)
                if st.button("🗑️", key=f"del_{it['id']}"):
                    delete_item(it["id"])
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

            st.markdown("</div>", unsafe_allow_html=True)

        if to_buy:
            # process after rendering to avoid mutation-while-iterating issues
            for item_id in to_buy:
                mark_bought(item_id)
                st.session_state[f"cb_{item_id}"] = False
            st.rerun()

    # Bought (simple)
    if show_bought:
        with st.expander(f"Købte ({len(bought_items)})", expanded=False):
            for it in bought_items[:120]:
                st.write(f"• {it.get('name','')} ×{it.get('qty',1)} — {human_time(it.get('bought_at'))}")


# =========================================================
# 🏠 HOME TAB
# =========================================================
with tab_home:
    st.subheader("Hjemme")
    home = list(S["home_items"])
    home.sort(key=lambda x: (norm(x.get("location", "")), norm(x.get("name", "")).lower()))

    if not home:
        st.info("Tom.")
    else:
        last_loc = ""
        for it in home:
            loc = norm(it.get("location", "")) or "Andet"
            if loc != last_loc:
                st.markdown(f"#### {loc}")
                last_loc = loc

            c1, c2, c3 = st.columns([6.9, 1.1, 1.4], vertical_alignment="center")
            with c1:
                st.write(it.get("name", ""))
            with c2:
                st.write(f"×{it.get('qty',1)}")
            with c3:
                if st.button("Brugt", key=f"used_{it['id']}"):
                    it["qty"] = max(0, int(it.get("qty", 1)) - 1)
                    it["last_used_at"] = now_iso()
                    persist()
                    # prompt minimal: add back immediately using memory (no modal)
                    nm = it.get("name", "")
                    mem = S["memory"].get(key(nm), {})
                    add_or_merge_shopping(
                        nm,
                        int(mem.get("default_qty", 1) or 1),
                        mem.get("category", "Andet"),
                        mem.get("store", S["settings"].get("default_store", "Netto")),
                    )
                    # remove if zero
                    if it["qty"] <= 0:
                        S["home_items"] = [x for x in S["home_items"] if x.get("id") != it["id"]]
                        persist()
                    st.rerun()


# =========================================================
# ⭐ STANDARD TAB
# =========================================================
with tab_std:
    st.subheader("Standard")

    std = list(S["standard_items"])
    std.sort(key=lambda x: (norm(x.get("category", "")), norm(x.get("name", "")).lower(), norm(x.get("store", ""))))

    if not std:
        st.info("Tom.")
    else:
        last_cat = ""
        for it in std:
            cat = norm(it.get("category", "")) or "Andet"
            if cat != last_cat:
                st.markdown(f"#### {cat}")
                last_cat = cat

            c1, c2, c3 = st.columns([6.9, 1.1, 1.4], vertical_alignment="center")
            with c1:
                st.write(it.get("name", ""))
            with c2:
                st.write(f"×{it.get('default_qty',1)}")
            with c3:
                if st.button("Tilføj", key=f"stdadd_{it['id']}"):
                    add_or_merge_shopping(
                        it.get("name", ""),
                        int(it.get("default_qty", 1)),
                        it.get("category", "Andet"),
                        it.get("store", S["settings"].get("default_store", "Netto")),
                    )
                    upsert_memory(
                        it.get("name", ""),
                        it.get("category", "Andet"),
                        it.get("store", S["settings"].get("default_store", "Netto")),
                        int(it.get("default_qty", 1)),
                        True,
                    )
                    st.rerun()


# =========================================================
# ⚙️ SETTINGS TAB
# =========================================================
with tab_settings:
    st.subheader("Indstillinger")

    S["settings"]["default_store"] = st.selectbox(
        "Default butik",
        S["stores"],
        index=S["stores"].index(S["settings"].get("default_store", "Netto")) if S["settings"].get("default_store", "Netto") in S["stores"] else 0,
        key="set_def_store",
    )
    S["settings"]["default_home_location"] = st.selectbox(
        "Default hjemme",
        S["home_locations"],
        index=S["home_locations"].index(S["settings"].get("default_home_location", "Køleskab")) if S["settings"].get("default_home_location", "Køleskab") in S["home_locations"] else 0,
        key="set_def_home",
    )
    S["settings"]["show_bought"] = st.toggle("Vis købte", value=bool(S["settings"].get("show_bought", False)), key="set_show_bought")
    persist()

    st.divider()

    c1, c2, c3 = st.columns(3, vertical_alignment="center")
    with c1:
        new_cat = st.text_input("Ny kategori", key="new_cat")
        if st.button("Tilføj", key="add_cat"):
            v = norm(new_cat)
            if v and v not in S["categories"]:
                S["categories"].insert(0, v)
                persist()
                st.rerun()

    with c2:
        new_store = st.text_input("Ny butik", key="new_store")
        if st.button("Tilføj", key="add_store"):
            v = norm(new_store)
            if v and v not in S["stores"]:
                S["stores"].insert(0, v)
                persist()
                st.rerun()

    with c3:
        new_loc = st.text_input("Nyt sted", key="new_loc")
        if st.button("Tilføj", key="add_loc"):
            v = norm(new_loc)
            if v and v not in S["home_locations"]:
                S["home_locations"].insert(0, v)
                persist()
                st.rerun()
