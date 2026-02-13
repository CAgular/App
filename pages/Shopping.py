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
st.caption("Hurtig, mobil-venlig indkøbsliste med standardvarer + hjemme-lager.")

# =========================================================
# Mobile-first styling (tighter list)
# =========================================================
st.markdown(
    """
    <style>
      .block-container { padding-top: 0.9rem; padding-bottom: 1.6rem; max-width: 720px; }

      /* Default buttons (big, thumb-friendly) */
      .stButton>button {
        width: 100%;
        padding: 0.70rem 0.90rem;
        border-radius: 16px;
        font-weight: 650;
      }

      /* Inputs */
      div[data-testid="stTextInput"] input,
      div[data-testid="stNumberInput"] input,
      div[data-testid="stSelectbox"] div {
        border-radius: 16px !important;
      }

      /* Compact card for list rows */
      .k-card {
        border: 1px solid rgba(49, 51, 63, 0.14);
        border-radius: 16px;
        padding: 0.50rem 0.70rem;
        margin: 0.22rem 0;              /* <— tighter spacing */
        background: rgba(255,255,255,0.02);
      }

      .k-title { font-weight: 750; font-size: 1.02rem; line-height: 1.2; }
      .k-muted { opacity: 0.72; font-size: 0.90rem; }

      /* Small +/- and trash buttons */
      .k-smallbtn .stButton>button {
        padding: 0.48rem 0.55rem;
        border-radius: 14px;
        font-weight: 750;
      }

      /* Reduce heading gaps a bit */
      h4 { margin-top: 0.55rem; margin-bottom: 0.20rem; }
      h3 { margin-top: 0.70rem; margin-bottom: 0.20rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

# =========================================================
# Persistence (hidden – no export UI)
# =========================================================
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
DATA_FILE = DATA_DIR / "shopping_v4.json"

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
    if "shopping_v4" in st.session_state:
        return
    data = load_data() or {}
    st.session_state.shopping_v4 = {
        "shopping_items": data.get("shopping_items", []),     # {id,name,qty,category,store,status,created_at,bought_at}
        "standard_items": data.get("standard_items", []),     # {id,name,default_qty,category,store}
        "home_items": data.get("home_items", []),             # {id,name,qty,location,category,store,added_at,last_used_at}
        "memory": data.get("memory", {}),                     # key=name_lower -> {name,category,store,default_qty,is_standard,updated_at}
        "stores": data.get("stores", DEFAULT_STORES),
        "categories": data.get("categories", DEFAULT_CATEGORIES),
        "home_locations": data.get("home_locations", DEFAULT_HOME_LOCATIONS),
        "settings": data.get(
            "settings",
            {
                "store_filter": "Alle",
                "default_store": data.get("settings", {}).get("default_store", "Netto") if isinstance(data.get("settings", {}), dict) else "Netto",
                "default_home_location": "Køleskab",
                "show_bought": False,
            },
        ),
        "used_prompt": None,
        "meta": data.get("meta", {"last_saved": None}),
    }


def persist():
    payload = {
        "shopping_items": st.session_state.shopping_v4["shopping_items"],
        "standard_items": st.session_state.shopping_v4["standard_items"],
        "home_items": st.session_state.shopping_v4["home_items"],
        "memory": st.session_state.shopping_v4["memory"],
        "stores": st.session_state.shopping_v4["stores"],
        "categories": st.session_state.shopping_v4["categories"],
        "home_locations": st.session_state.shopping_v4["home_locations"],
        "settings": st.session_state.shopping_v4["settings"],
        "meta": {"last_saved": now_iso()},
    }
    save_data(payload)
    st.session_state.shopping_v4["meta"]["last_saved"] = payload["meta"]["last_saved"]


ensure_state()
S = st.session_state.shopping_v4


def normalize_name(name: str) -> str:
    return (name or "").strip()


def key(name: str) -> str:
    return normalize_name(name).lower()


def ensure_ids(items: List[Dict]) -> List[Dict]:
    out = []
    for it in items:
        d = dict(it)
        d.setdefault("id", str(uuid.uuid4()))
        out.append(d)
    return out


S["shopping_items"] = ensure_ids(S["shopping_items"])
S["standard_items"] = ensure_ids(S["standard_items"])
S["home_items"] = ensure_ids(S["home_items"])


def upsert_memory(name: str, category: str, store: str, default_qty: int, is_standard: bool):
    k = key(name)
    if not k:
        return
    S["memory"][k] = {
        "name": normalize_name(name),
        "category": category,
        "store": store,
        "default_qty": int(default_qty),
        "is_standard": bool(is_standard),
        "updated_at": now_iso(),
    }


def suggestions(prefix: str, limit: int = 8) -> List[Dict]:
    p = (prefix or "").strip().lower()
    if not p:
        return []
    hits = []
    for _, v in S["memory"].items():
        nm = (v.get("name") or "").strip()
        if nm.lower().startswith(p):
            hits.append(v)
    hits.sort(key=lambda x: (len(x.get("name", "")), x.get("updated_at", "")))
    return hits[:limit]


def add_or_merge_shopping(name: str, qty: int, category: str, store: str):
    name = normalize_name(name)
    if not name:
        return
    qty = max(1, int(qty))
    for it in S["shopping_items"]:
        if it.get("status", "open") == "open" and key(it.get("name", "")) == key(name) and it.get("category") == category and it.get("store") == store:
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
        if key(it.get("name", "")) == key(name) and it.get("category") == category and it.get("store") == store:
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
        if key(h.get("name", "")) == key(name) and h.get("location") == location:
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
            add_to_home(it["name"], int(it.get("qty", 1)), default_loc, it.get("category", "Andet"), it.get("store", "Andet"))
            return


def change_qty(item_id: str, delta: int):
    for it in S["shopping_items"]:
        if it["id"] == item_id and it.get("status") == "open":
            it["qty"] = max(1, int(it.get("qty", 1)) + int(delta))
            persist()
            return


def delete_open_item(item_id: str):
    S["shopping_items"] = [x for x in S["shopping_items"] if x["id"] != item_id]
    persist()


# =========================================================
# Layout
# =========================================================
tab_shop, tab_home, tab_std, tab_settings = st.tabs(["🧾 Indkøb", "🏠 Hjemme", "⭐ Standard", "⚙️"])

# -------------------------
# 🧾 INDKØB
# -------------------------
with tab_shop:
    st.subheader("➕ Tilføj")

    # Form resets fields on submit; qty should default back to 1 after submit
    with st.form("add_item_form", clear_on_submit=True):
        name = st.text_input("Vare", placeholder="Skriv fx: bananer")

        mem = S["memory"].get(key(name)) if name else None

        # Default values: use memory for category/store/standard; qty is memory while typing,
        # but after submit (name clears) qty will show 1.
        cat_default = mem.get("category", "Andet") if mem else "Andet"
        store_fallback = S["settings"].get("default_store", "Netto")
        store_default = mem.get("store", store_fallback) if mem else store_fallback

        qty_default = int(mem.get("default_qty", 1) if mem else 1)
        std_default = bool(mem.get("is_standard", False) if mem else False)

        category = st.selectbox(
            "Kategori",
            S["categories"],
            index=S["categories"].index(cat_default) if cat_default in S["categories"] else 0,
        )
        store = st.selectbox(
            "Butik",
            S["stores"],
            index=S["stores"].index(store_default) if store_default in S["stores"] else 0,
        )

        # qty defaults to remembered qty while typing exact match; resets to 1 once form is cleared
        qty = st.number_input("Antal", min_value=1, value=max(1, qty_default), step=1)

        is_standard = st.checkbox("⭐ Standardvare", value=std_default)

        submit = st.form_submit_button("✅ Tilføj til indkøbslisten")
        if submit:
            clean = normalize_name(name)
            if not clean:
                st.warning("Skriv et varenavn.")
            else:
                add_or_merge_shopping(clean, int(qty), category, store)
                upsert_memory(clean, category, store, int(qty), is_standard)
                if is_standard:
                    add_or_update_standard(clean, int(qty), category, store)

                st.success("Tilføjet ✅")
                st.rerun()

    with st.expander("✨ Forslag (fra historik)", expanded=False):
        pref = st.text_input("Skriv start (fx 'ban')", key="pref_sug")
        for sug in suggestions(pref, limit=10):
            label = f"{sug.get('name','')} (antal {sug.get('default_qty',1)})"
            if st.button(label, key=f"prefpick_{key(sug.get('name',''))}_{sug.get('store','')}_{sug.get('category','')}"):
                add_or_merge_shopping(
                    sug.get("name", ""),
                    int(sug.get("default_qty", 1)),
                    sug.get("category", "Andet"),
                    sug.get("store", S["settings"].get("default_store", "Netto")),
                )
                st.success("Tilføjet ✅")
                st.rerun()

    st.divider()

    settings = S["settings"]
    stores = ["Alle"] + S["stores"]

    with st.expander("Filtre", expanded=False):
        settings["store_filter"] = st.selectbox(
            "Butik",
            stores,
            index=stores.index(settings.get("store_filter", "Alle")) if settings.get("store_filter", "Alle") in stores else 0,
        )
        settings["show_bought"] = st.toggle("Vis købte varer", value=bool(settings.get("show_bought", False)))
        S["settings"] = settings
        persist()

    search = st.text_input("Søg i indkøb", placeholder="Søg…")

    items = list(S["shopping_items"])
    if settings.get("store_filter", "Alle") != "Alle":
        items = [x for x in items if x.get("store") == settings["store_filter"]]
    if search.strip():
        q = search.strip().lower()
        items = [x for x in items if q in (x.get("name", "").lower())]

    open_items = [x for x in items if x.get("status") == "open"]
    bought_items = [x for x in items if x.get("status") == "bought"]

    open_items.sort(key=lambda x: (x.get("store", ""), x.get("category", ""), x.get("name", "").lower()))
    bought_items.sort(key=lambda x: (x.get("bought_at") or ""), reverse=True)

    st.subheader("🧾 Indkøbsliste")
    if not open_items:
        st.info("Ingen varer på listen.")
    else:
        last_group = None
        for it in open_items:
            group = f"{it.get('store','')} · {it.get('category','')}"
            if group != last_group:
                st.markdown(f"#### {group}")
                last_group = group

            st.markdown('<div class="k-card">', unsafe_allow_html=True)

            # One compact row: name + qty + (-/+) on same line
            # (columns can wrap a bit on very small screens, but stays compact)
            c_name, c_minus, c_qty, c_plus = st.columns([7, 1.2, 1.2, 1.2], vertical_alignment="center")

            with c_name:
                st.markdown(f'<div class="k-title">{it.get("name","")}</div>', unsafe_allow_html=True)

            with c_minus:
                st.markdown('<div class="k-smallbtn">', unsafe_allow_html=True)
                if st.button("➖", key=f"m_{it['id']}"):
                    change_qty(it["id"], -1)
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

            with c_qty:
                st.markdown(f"<div class='k-muted' style='text-align:center; font-weight:700;'>{it.get('qty',1)}</div>", unsafe_allow_html=True)

            with c_plus:
                st.markdown('<div class="k-smallbtn">', unsafe_allow_html=True)
                if st.button("➕", key=f"p_{it['id']}"):
                    change_qty(it["id"], +1)
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

            # Buttons row: BUY big, REMOVE small
            b_buy, b_del = st.columns([4, 1.3], vertical_alignment="center")
            with b_buy:
                if st.button("✅ Købt", key=f"buy_{it['id']}"):
                    mark_bought(it["id"])
