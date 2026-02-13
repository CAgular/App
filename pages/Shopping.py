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
      .block-container { padding-top: 0.85rem; padding-bottom: 1.5rem; max-width: 720px; }

      .stButton>button {
        width: 100%;
        padding: 0.68rem 0.88rem;
        border-radius: 16px;
        font-weight: 650;
      }

      div[data-testid="stTextInput"] input,
      div[data-testid="stNumberInput"] input,
      div[data-testid="stSelectbox"] div {
        border-radius: 16px !important;
      }

      .k-card {
        border: 1px solid rgba(49, 51, 63, 0.14);
        border-radius: 16px;
        padding: 0.46rem 0.65rem;
        margin: 0.18rem 0;          /* tighter spacing */
        background: rgba(255,255,255,0.02);
      }

      .k-title { font-weight: 760; font-size: 1.02rem; line-height: 1.15; }
      .k-muted { opacity: 0.72; font-size: 0.90rem; }

      .k-smallbtn .stButton>button {
        padding: 0.46rem 0.52rem;
        border-radius: 14px;
        font-weight: 760;
      }

      h4 { margin-top: 0.50rem; margin-bottom: 0.18rem; }
      h3 { margin-top: 0.65rem; margin-bottom: 0.18rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

# =========================================================
# Persistence (hidden – no export UI)
# =========================================================
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
DATA_FILE = DATA_DIR / "shopping_v5.json"

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
    if "shopping_v5" in st.session_state:
        return

    data = load_data() or {}
    settings = data.get("settings", {}) if isinstance(data.get("settings", {}), dict) else {}

    st.session_state.shopping_v5 = {
        "shopping_items": data.get("shopping_items", []),     # {id,name,qty,category,store,status,created_at,bought_at}
        "standard_items": data.get("standard_items", []),     # {id,name,default_qty,category,store}
        "home_items": data.get("home_items", []),             # {id,name,qty,location,category,store,added_at,last_used_at}
        "memory": data.get("memory", {}),                     # key=name_lower -> {name,category,store,default_qty,is_standard,updated_at}
        "stores": data.get("stores", DEFAULT_STORES),
        "categories": data.get("categories", DEFAULT_CATEGORIES),
        "home_locations": data.get("home_locations", DEFAULT_HOME_LOCATIONS),
        "settings": {
            "store_filter": settings.get("store_filter", "Alle"),
            "default_store": settings.get("default_store", "Netto"),
            "default_home_location": settings.get("default_home_location", "Køleskab"),
            "show_bought": settings.get("show_bought", False),
        },
        "used_prompt": None,
        "meta": data.get("meta", {"last_saved": None}),
    }


def persist():
    S = st.session_state.shopping_v5
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


ensure_state()
S = st.session_state.shopping_v5


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


def suggestions(prefix: str, limit: int = 10) -> List[Dict]:
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

    # merge with existing open
    for it in S["shopping_items"]:
        if (
            it.get("status", "open") == "open"
            and key(it.get("name", "")) == key(name)
            and it.get("category") == category
            and it.get("store") == store
        ):
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

    # merge by name+location
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
            # always add to home
            add_to_home(
                it.get("name", ""),
                int(it.get("qty", 1)),
                default_loc,
                it.get("category", "Andet"),
                it.get("store", S["settings"].get("default_store", "Netto")),
            )
            return


def change_qty(item_id: str, delta: int):
    for it in S["shopping_items"]:
        if it["id"] == item_id and it.get("status") == "open":
            it["qty"] = max(1, int(it.get("qty", 1)) + int(delta))
            persist()
            return


def delete_open_item(item_id: str)_
