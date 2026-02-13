import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

import streamlit as st
from src.config import APP_TITLE

# =========================================================
# Page config + nav
# =========================================================
st.set_page_config(page_title=f"{APP_TITLE} • Shopping", page_icon="🛒", layout="centered")
st.link_button("⬅️ Tilbage til forside", "/")

st.title("🛒 Shopping")

# =========================================================
# Styling: compact + iPhone-friendly, no row tips
# =========================================================
st.markdown(
    """
    <style>
      .block-container { padding-top: 0.65rem; padding-bottom: 1.1rem; max-width: 720px; }

      /* Make Streamlit spacing tighter */
      div[data-testid="stVerticalBlock"] { gap: 0.28rem; }
      h4 { margin-top: 0.35rem; margin-bottom: 0.10rem; }
      h3 { margin-top: 0.45rem; margin-bottom: 0.10rem; }

      /* Inputs rounded */
      div[data-testid="stTextInput"] input,
      div[data-testid="stNumberInput"] input,
      div[data-testid="stSelectbox"] div {
        border-radius: 14px !important;
      }

      /* Buttons: not full width */
      .stButton>button {
        width: auto;
        padding: 0.46rem 0.62rem;
        border-radius: 14px;
        font-weight: 650;
      }

      /* Tiny icon button */
      .btn-icon .stButton>button {
        width: 40px;
        min-width: 40px;
        height: 36px;
        padding: 0;
        border-radius: 12px;
        font-weight: 850;
      }

      /* Make checkboxes smaller (best-effort) */
      div[data-testid="stCheckbox"] input[type="checkbox"]{
        transform: scale(0.85);
        transform-origin: left center;
      }

      /* Compact row look */
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
    </style>
    """,
    unsafe_allow_html=True,
)

# =========================================================
# Persistence
# =========================================================
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
DATA_FILE = DATA_DIR / "shopping_simple_v1.json"

DEFAULT_STORES = ["Netto", "Rema 1000", "Føtex", "Lidl", "Apotek", "Bauhaus", "Andet"]
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


def ensure_state():
    if "shopping_simple" in st.session_state:
        return

    data = load_data() or {}
    settings = data.get("settings", {}) if isinstance(data.get("settings", {}), dict) else {}

    st.session_state.shopping_simple = {
        "shopping_items": data.get("shopping_items", []),   # open + bought in same list
        "standard_items": data.get("standard_items", []),
        "home_items": data.get("home_items", []),
        "memory": data.get("memory", {}),
        "stores": data.get("stores", DEFAULT_STORES),
        "categories": data.get("categories", DEFAULT_CATEGORIES),
        "home_locations": data.get("home_locations", DEFAULT_HOME_LOCATIONS),
        "settings": {
            "store_filter": settings.get("store_filter", "Alle"),
            "default_store": settings.get("default_store", "Netto"),
            "default_home_location": settings.get("default_home_location", "Køleskab"),
            "show_bought": settings.get("show_bought", False),
        },
        "meta": data.get("meta", {"last_saved": None}),
    }


def persist():
    S = st.session_state.shopping_simple
    payload = {
        "shopping_items": S["shopping_items"],
        "standard_items": S["standard_items"],
        "home_items": S["home_items"],
        "memory": S["memory"],
        "stores": S["stores"],
        "categories": S["categories"],
        "home_locations": S["home_locations"],
        "settings": S["settings"],
        "meta": {"last_saved": now_iso()},
    }
    save_data(payload)
    S["meta"]["last_saved"] = payload["meta"]["last_saved"]


def ensure_ids(items: List[Dict]) -> List[Dict]:
    out = []
    for it in items:
        d = dict(it)
        d.setdefault("id", str(uuid.uuid4()))
        out.append(d)
    return out


def normalize_name(name: str) -> str:
    return (name or "").strip()


def k(name: str) -> str:
    return normalize_name(name).lower()


ensure_state()
S = st.session_state.shopping_simple
S["shopping_items"] = ensure_ids(S["shopping_items"])
S["standard_items"] = ensure_ids(S["standard_items"])
S["home_items"] = ensure_ids(S["home_items"])


# =========================================================
# Core operations
# =========================================================
def upsert_memory(name: str, category: str, store: str, default_qty: int, is_standard: bool):
    kk = k(name)
    if not kk:
        return
    S["memory"][kk] = {
        "name": normalize_name(name),
        "category": category,
        "store": store,
        "default_qty": int(default_qty),
        "is_standard": bool(is_standard),
        "updated_at": now_iso(),
    }


def suggestions(prefix: str, limit: int = 10) -> List[Dict]:
    p = (prefix or "").strip().lower()
    if not p:
        return []
    hits = [v for v in S["memory"].values() if (v.get("name") or "").lower().startswith(p)]
    hits.sort(key=lambda x: (len(x.get("name", "")), x.get("updated_at", "")))
    return hits[:limit]


def add_or_merge_shopping(name: str, qty: int, category: str, store: str):
    name = normalize_name(name)
    if not name:
        return

    qty = max(1, int(qty))
    # merge only with same name+cat+store and status open
    for it in S["shopping_items"]:
        if it.get("status") == "open" and k(it.get("name", "")) == k(name) and it.get("category") == category and it.get("store") == store:
            it["qty"] = int(it.get("qty", 1)) + qty
            persist()
            return

    S["shopping_items"].append(
        {
            "id": str(uuid.uuid4()),
            "name": name,
            "qty": qty,
            "category": category,
            "store": store,
            "status": "open",
            "created_at": now_iso(),
            "bought_at": None,
        }
    )
    persist()


def add_or_update_standard(name: str, default_qty: int, category: str, store: str):
    name = normalize_name(name)
    if not name:
        return
    for it in S["standard_items"]:
        if k(it.get("name", "")) == k(name) and it.get("category") == category and it.get("store") == store:
            it["default_qty"] = max(1, int(default_qty))
            persist()
            return
    S["standard_items"].append(
        {"id": str(uuid.uuid4()), "name": name, "default_qty": max(1, int(default_qty)), "category": category, "store": store}
    )
    persist()


def add_to_home(name: str, qty: int, location: str, category: str, store: str):
    name = normalize_name(name)
    if not name:
        return
    qty = max(1, int(qty))

    for h in S["home_items"]:
        if k(h.get("name", "")) == k(name) and h.get("location") == location:
            h["qty"] = int(h.get("qty", 1)) + qty
            h["category"] = category
            h["store"] = store
            h["added_at"] = now_iso()
            persist()
            return

    S["home_items"].append(
        {
            "id": str(uuid.uuid4()),
            "name": name,
            "qty": qty,
            "location": location,
            "category": category,
            "store": store,
            "added_at": now_iso(),
            "last_used_at": None,
        }
    )
    persist()


def mark_bought(item_id: str):
    default_loc = S["settings"].get("default_home_location", "Køleskab")
    for it in S["shopping_items"]:
        if it["id"] == item_id and it.get("status") == "open":
            it["status"] = "bought"
            it["bought_at"] = now_iso()
            persist()
            add_to_home(
                it.get("name", ""),
                int(it.get("qty", 1)),
                default_loc,
                it.get("category", "Andet"),
                it.get("store", S["settings"].get("default_store", "Netto")),
            )
            return


def delete_item(item_id: str):
    S["shopping_items"] = [x for x in S["shopping_items"] if x["id"] != item_id]
    persist()


# =========================================================
# Checkbox callback (instant buy, no extra buttons/tips)
# =========================================================
st.session_state.setdefault("_do_rerun", False)


def on_bought_toggle(item_id: str, cb_key: str):
    # if checked -> buy instantly, then reset checkbox state so it doesn't stay ticked
    if st.session_state.get(cb_key, False):
        mark_bought(item_id)
        st.session_state[cb_key] = False
        st.session_state["_do_rerun"] = True


# =========================================================
# Add-form: stable reset pattern
# =========================================================
K_NAME = "add_name"
K_CAT = "add_category"
K_STORE = "add_store"
K_QTY = "add_qty"
K_STD = "add_standard"
K_LAST_AUTOFILL = "last_autofill_name"
K_RESET = "add_form_reset"

st.session_state.setdefault(K_NAME, "")
st.session_state.setdefault(K_CAT, "Andet")
st.session_state.setdefault(K_STORE, S["settings"].get("default_store", "Netto"))
st.session_state.setdefault(K_QTY, 1)
st.session_state.setdefault(K_STD, False)
st.session_state.setdefault(K_LAST_AUTOFILL, "")
st.session_state.setdefault(K_RESET, False)


def reset_add_form():
    st.session_state[K_NAME] = ""
    st.session_state[K_QTY] = 1
    st.session_state[K_STD] = False
    st.session_state[K_LAST_AUTOFILL] = ""
    st.session_state[K_RESET] = False


def maybe_autofill():
    nm = normalize_name(st.session_state.get(K_NAME, ""))
    if not nm:
        return
    mk = k(nm)
    mem = S["memory"].get(mk)
    if mem and st.session_state.get(K_LAST_AUTOFILL, "") != mk:
        st.session_state[K_CAT] = mem.get("category", st.session_state[K_CAT])
        st.session_state[K_STORE] = mem.get("store", st.session_state[K_STORE])
        st.session_state[K_STD] = bool(mem.get("is_standard", st.session_state[K_STD]))
        st.session_state[K_QTY] = int(mem.get("default_qty", st.session_state[K_QTY]) or 1)
        st.session_state[K_LAST_AUTOFILL] = mk


# =========================================================
# Tabs
# =========================================================
tab_shop, tab_home, tab_std, tab_settings = st.tabs(["🧾 Indkøb", "🏠 Hjemme", "⭐ Standard", "⚙️ Indstillinger"])

# =========================================================
# 🧾 SHOPPING
# =========================================================
with tab_shop:
    # Add
    if st.session_state.get(K_RESET, False):
        reset_add_form()

    maybe_autofill()

    with st.form("add_item_form", clear_on_submit=False):
        st.text_input("Vare", placeholder="Skriv fx: bananer", key=K_NAME)
        c1, c2 = st.columns([1, 1], vertical_alignment="center")
        with c1:
            st.selectbox("Kategori", S["categories"], key=K_CAT)
        with c2:
            st.selectbox("Butik", S["stores"], key=K_STORE)
        c3, c4 = st.columns([1, 1], vertical_alignment="center")
        with c3:
            st.number_input("Antal", min_value=1, step=1, key=K_QTY)
        with c4:
            st.checkbox("Standardvare", key=K_STD)

        submit = st.form_submit_button("Tilføj")

    if submit:
        nm = normalize_name(st.session_state.get(K_NAME, ""))
        if nm:
            category = st.session_state.get(K_CAT, "Andet")
            store = st.session_state.get(K_STORE, S["settings"].get("default_store", "Netto"))
            qty = int(st.session_state.get(K_QTY, 1) or 1)
            is_std = bool(st.session_state.get(K_STD, False))

            add_or_merge_shopping(nm, qty, category, store)
            upsert_memory(nm, category, store, qty, is_std)
            if is_std:
                add_or_update_standard(nm, qty, category, store)

            st.session_state[K_RESET] = True
            st.rerun()
        else:
            st.warning("Skriv et varenavn.")

    # Suggestions (minimal)
    with st.expander("Forslag", expanded=False):
        pref = st.text_input("Start", placeholder="fx ban", key="pref_sug")
        for sug in suggestions(pref, limit=10):
            if st.button(sug.get("name", ""), key=f"sug_{k(sug.get('name',''))}"):
                st.session_state[K_NAME] = sug.get("name", "")
                st.session_state[K_CAT] = sug.get("category", "Andet")
                st.session_state[K_STORE] = sug.get("store", S["settings"].get("default_store", "Netto"))
                st.session_state[K_QTY] = int(sug.get("default_qty", 1) or 1)
                st.session_state[K_STD] = bool(sug.get("is_standard", False))
                st.session_state[K_LAST_AUTOFILL] = k(sug.get("name", ""))
                st.rerun()

    # Filters (minimal)
    with st.expander("Filtre", expanded=False):
        stores = ["Alle"] + S["stores"]
        S["settings"]["store_filter"] = st.selectbox(
            "Butik",
            stores,
            index=stores.index(S["settings"].get("store_filter", "Alle")) if S["settings"].get("store_filter", "Alle") in stores else 0,
            key="filter_store",
        )
        S["settings"]["show_bought"] = st.toggle("Vis købte", value=bool(S["settings"].get("show_bought", False)), key="toggle_bought")
        persist()

    search = st.text_input("Søg", placeholder="Søg…", key="shop_search")

    items = list(S["shopping_items"])
    if S["settings"].get("store_filter", "Alle") != "Alle":
        items = [x for x in items if x.get("store") == S["settings"]["store_filter"]]
    if search.strip():
        q = search.strip().lower()
        items = [x for x in items if q in (x.get("name", "").lower())]

    open_items = [x for x in items if x.get("status") == "open"]
    bought_items = [x for x in items if x.get("status") == "bought"]

    open_items.sort(key=lambda x: (x.get("store", ""), x.get("category", ""), x.get("name", "").lower()))
    bought_items.sort(key=lambda x: (x.get("bought_at") or ""), reverse=True)

    st.subheader("Indkøbsliste")

    if not open_items:
        st.info("Tom.")
    else:
        last_group = None
        for it in open_items:
            group = f"{it.get('store','')} · {it.get('category','')}"
            if group != last_group:
                st.markdown(f"#### {group}")
                last_group = group

            st.markdown('<div class="row">', unsafe_allow_html=True)

            # Compact one-row: checkbox | name | qty | delete
            c_cb, c_name, c_qty, c_del = st.columns([0.8, 6.8, 1.1, 1.0], vertical_alignment="center")

            cb_key = f"buycb_{it['id']}"
            with c_cb:
                st.checkbox(
                    "købt",
                    key=cb_key,
                    label_visibility="collapsed",
                    on_change=on_bought_toggle,
                    args=(it["id"], cb_key),
                )

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

        if st.session_state.get("_do_rerun", False):
            st.session_state["_do_rerun"] = False
            st.rerun()

    if S["settings"].get("show_bought", False):
        with st.expander(f"Købte ({len(bought_items)})", expanded=False):
            for it in bought_items[:120]:
                st.write(f"• {it.get('name','')} ×{it.get('qty',1)} — {human_time(it.get('bought_at'))}")

# =========================================================
# 🏠 HOME
# =========================================================
with tab_home:
    st.subheader("Hjemme")

    st.session_state.setdefault("used_name_prompt", "")

    q = st.text_input("Søg", placeholder="Søg…", key="home_search")

    home = list(S["home_items"])
    if q.strip():
        qq = q.strip().lower()
        home = [x for x in home if qq in (x.get("name", "").lower())]
    home.sort(key=lambda x: (x.get("location", ""), x.get("name", "").lower()))

    if not home:
        st.info("Tom.")
    else:
        last_loc = None
        for it in home:
            loc = it.get("location", "Andet")
            if loc != last_loc:
                st.markdown(f"#### {loc}")
                last_loc = loc

            c1, c2, c3 = st.columns([6.8, 1.1, 1.4], vertical_alignment="center")
            with c1:
                st.write(it.get("name", ""))
            with c2:
                st.write(f"×{it.get('qty',1)}")
            with c3:
                if st.button("Brugt", key=f"used_{it['id']}"):
                    it["qty"] = max(0, int(it.get("qty", 1)) - 1)
                    it["last_used_at"] = now_iso()
                    if it["qty"] <= 0:
                        S["home_items"] = [x for x in S["home_items"] if x["id"] != it["id"]]
                    persist()
                    st.session_state["used_name_prompt"] = it.get("name", "")
                    st.rerun()

        used_nm = st.session_state.get("used_name_prompt", "")
        if used_nm:
            st.divider()
            cA, cB = st.columns([2, 1], vertical_alignment="center")
            with cA:
                if st.button("Tilføj til indkøb", key="used_add"):
                    mem = S["memory"].get(k(used_nm), {})
                    add_or_merge_shopping(
                        used_nm,
                        int(mem.get("default_qty", 1) or 1),
                        mem.get("category", "Andet"),
                        mem.get("store", S["settings"].get("default_store", "Netto")),
                    )
                    st.session_state["used_name_prompt"] = ""
                    st.rerun()
            with cB:
                if st.button("Luk", key="used_close"):
                    st.session_state["used_name_prompt"] = ""
                    st.rerun()

# =========================================================
# ⭐ STANDARD
# =========================================================
with tab_std:
    st.subheader("Standard")

    q = st.text_input("Søg", placeholder="Søg…", key="std_search")
    std = list(S["standard_items"])
    if q.strip():
        qq = q.strip().lower()
        std = [x for x in std if qq in (x.get("name", "").lower())]

    std.sort(key=lambda x: (x.get("category", ""), x.get("name", "").lower(), x.get("store", "")))

    if not std:
        st.info("Tom.")
    else:
        last_cat = None
        for it in std:
            cat = it.get("category", "Andet")
            if cat != last_cat:
                st.markdown(f"#### {cat}")
                last_cat = cat

            c1, c2, c3 = st.columns([6.8, 1.1, 1.4], vertical_alignment="center")
            with c1:
                st.write(it.get("name", ""))
            with c2:
                st.write(f"×{it.get('default_qty',1)}")
            with c3:
                if st.button("Tilføj", key=f"stdadd_{it['id']}"):
                    add_or_merge_shopping(
                        it["name"],
                        int(it.get("default_qty", 1)),
                        it.get("category", "Andet"),
                        it.get("store", S["settings"].get("default_store", "Netto")),
                    )
                    upsert_memory(
                        it["name"],
                        it.get("category", "Andet"),
                        it.get("store", S["settings"].get("default_store", "Netto")),
                        int(it.get("default_qty", 1)),
                        True,
                    )
                    st.rerun()

# =========================================================
# ⚙️ SETTINGS
# =========================================================
with tab_settings:
    st.subheader("Indstillinger")

    S["settings"]["default_store"] = st.selectbox(
        "Default butik",
        S["stores"],
        index=S["stores"].index(S["settings"].get("default_store", "Netto")) if S["settings"].get("default_store", "Netto") in S["stores"] else 0,
        key="set_default_store",
    )
    S["settings"]["default_home_location"] = st.selectbox(
        "Default hjemme",
        S["home_locations"],
        index=S["home_locations"].index(S["settings"].get("default_home_location", "Køleskab")) if S["settings"].get("default_home_location", "Køleskab") in S["home_locations"] else 0,
        key="set_default_home",
    )
    persist()

    st.divider()

    # Add lists (minimal, no extra text)
    c1, c2, c3 = st.columns(3, vertical_alignment="center")
    with c1:
        new_store = st.text_input("Ny butik", key="new_store")
        if st.button("Tilføj", key="add_store"):
            ns = (new_store or "").strip()
            if ns and ns not in S["stores"]:
                S["stores"].append(ns)
                persist()
                st.rerun()

    with c2:
        new_cat = st.text_input("Ny kategori", key="new_cat")
        if st.button("Tilføj", key="add_cat"):
            nc = (new_cat or "").strip()
            if nc and nc not in S["categories"]:
                S["categories"].append(nc)
                persist()
                st.rerun()

    with c3:
        new_loc = st.text_input("Nyt sted", key="new_loc")
        if st.button("Tilføj", key="add_loc"):
            nl = (new_loc or "").strip()
            if nl and nl not in S["home_locations"]:
                S["home_locations"].append(nl)
                persist()
                st.rerun()
