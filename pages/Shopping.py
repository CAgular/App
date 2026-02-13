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
# Mobile-first styling
# =========================================================
st.markdown(
    """
    <style>
      .block-container { padding-top: 1.0rem; padding-bottom: 2.0rem; max-width: 720px; }
      .stButton>button {
        width: 100%;
        padding: 0.72rem 0.95rem;
        border-radius: 16px;
        font-weight: 650;
      }
      div[data-testid="stTextInput"] input,
      div[data-testid="stNumberInput"] input,
      div[data-testid="stSelectbox"] div {
        border-radius: 16px !important;
      }
      .k-card {
        border: 1px solid rgba(49, 51, 63, 0.15);
        border-radius: 18px;
        padding: 0.85rem 0.9rem;
        margin: 0.55rem 0;
        background: rgba(255,255,255,0.03);
      }
      .k-title { font-weight: 750; font-size: 1.05rem; margin-bottom: 0.2rem; }
      .k-muted { opacity: 0.78; font-size: 0.92rem; }
      .k-inline { display:flex; gap:0.5rem; align-items:center; }
      .k-inline > div { flex: 1; }
      /* smaller +/- buttons */
      .k-smallbtn .stButton>button {
        padding: 0.55rem 0.65rem;
        border-radius: 14px;
        font-weight: 700;
      }
    </style>
    """,
    unsafe_allow_html=True,
)

# =========================================================
# Persistence (hidden – no export UI)
# =========================================================
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
DATA_FILE = DATA_DIR / "shopping_v3.json"

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
    if "shopping_v3" in st.session_state:
        return
    data = load_data() or {}
    st.session_state.shopping_v3 = {
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
                "default_home_location": "Køleskab",
                "show_bought": False,
            },
        ),
        "used_prompt": None,
        "meta": data.get("meta", {"last_saved": None}),
    }


def persist():
    payload = {
        "shopping_items": st.session_state.shopping_v3["shopping_items"],
        "standard_items": st.session_state.shopping_v3["standard_items"],
        "home_items": st.session_state.shopping_v3["home_items"],
        "memory": st.session_state.shopping_v3["memory"],
        "stores": st.session_state.shopping_v3["stores"],
        "categories": st.session_state.shopping_v3["categories"],
        "home_locations": st.session_state.shopping_v3["home_locations"],
        "settings": st.session_state.shopping_v3["settings"],
        "meta": {"last_saved": now_iso()},
    }
    save_data(payload)
    st.session_state.shopping_v3["meta"]["last_saved"] = payload["meta"]["last_saved"]


ensure_state()
S = st.session_state.shopping_v3


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


def suggestions(prefix: str, limit: int = 6) -> List[Dict]:
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
        {
            "id": str(uuid.uuid4()),
            "name": name,
            "default_qty": max(1, int(default_qty)),
            "category": category,
            "store": store,
        }
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

    # defaults from memory if exact match
    # Use a form so fields reset on submit (mobile-friendly)
    with st.form("add_item_form", clear_on_submit=True):
        name = st.text_input("Vare", placeholder="Skriv fx: bananer")
        mem = S["memory"].get(key(name)) if name else None

        cat_default = mem.get("category", "Andet") if mem else "Andet"
        store_default = mem.get("store", "Netto") if mem else "Netto"
        qty_default = int(mem.get("default_qty", 1) if mem else 1)
        std_default = bool(mem.get("is_standard", False) if mem else False)

        category = st.selectbox("Kategori", S["categories"], index=S["categories"].index(cat_default) if cat_default in S["categories"] else 0)
        store = st.selectbox("Butik", S["stores"], index=S["stores"].index(store_default) if store_default in S["stores"] else 0)
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

    # Suggestion buttons (outside form – live while typing is limited in Streamlit forms)
    # To keep it simple on mobile, we offer a small search box for suggestions:
    st.markdown("<div class='k-spacer'></div>", unsafe_allow_html=True)
    with st.expander("✨ Hurtige forslag (fra historik)", expanded=False):
        pref = st.text_input("Søg/skriv start (fx 'ban')", key="pref_sug")
        for sug in suggestions(pref, limit=8):
            label = f"{sug.get('name','')} · {sug.get('store','')} / {sug.get('category','')} (antal {sug.get('default_qty',1)})"
            if st.button(label, key=f"prefpick_{key(sug.get('name',''))}_{sug.get('store','')}_{sug.get('category','')}"):
                add_or_merge_shopping(
                    sug.get("name", ""),
                    int(sug.get("default_qty", 1)),
                    sug.get("category", "Andet"),
                    sug.get("store", "Netto"),
                )
                st.success("Tilføjet ✅")
                st.rerun()

    st.divider()

    # Filters (simple)
    settings = S["settings"]
    stores = ["Alle"] + S["stores"]

    with st.expander("Filtre", expanded=False):
        settings["store_filter"] = st.selectbox("Butik", stores, index=stores.index(settings.get("store_filter", "Alle")) if settings.get("store_filter", "Alle") in stores else 0)
        settings["show_bought"] = st.toggle("Vis købte varer", value=bool(settings.get("show_bought", False)))
        S["settings"] = settings
        persist()

    search = st.text_input("Søg i indkøb", placeholder="Søg…")

    # Build open list
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
            st.markdown(f'<div class="k-title">{it.get("name","")} · {it.get("qty",1)}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="k-muted">{it.get("store","")} · {it.get("category","")}</div>', unsafe_allow_html=True)

            bought = st.checkbox("Købt", value=False, key=f"b_{it['id']}")
            if bought:
                mark_bought(it["id"])
                st.rerun()

            # Minimal controls: qty +/- and delete (no expanders)
            c1, c2, c3 = st.columns([1, 1, 2])
            with c1:
                st.markdown('<div class="k-smallbtn">', unsafe_allow_html=True)
                if st.button("➖", key=f"m_{it['id']}"):
                    change_qty(it["id"], -1)
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
            with c2:
                st.markdown('<div class="k-smallbtn">', unsafe_allow_html=True)
                if st.button("➕", key=f"p_{it['id']}"):
                    change_qty(it["id"], +1)
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)
            with c3:
                if st.button("🗑️ Fjern", key=f"d_{it['id']}"):
                    delete_open_item(it["id"])
                    st.rerun()

            st.markdown("</div>", unsafe_allow_html=True)

    if settings.get("show_bought", False):
        with st.expander(f"✅ Købte varer ({len(bought_items)})", expanded=False):
            if not bought_items:
                st.caption("Ingen købte varer.")
            else:
                for it in bought_items[:60]:
                    st.markdown('<div class="k-card">', unsafe_allow_html=True)
                    st.markdown(f'<div class="k-title">{it.get("name","")} · {it.get("qty",1)}</div>', unsafe_allow_html=True)
                    st.markdown(f'<div class="k-muted">Købt: {human_time(it.get("bought_at"))}</div>', unsafe_allow_html=True)
                    st.markdown("</div>", unsafe_allow_html=True)


# -------------------------
# 🏠 HJEMME
# -------------------------
with tab_home:
    st.subheader("🏠 Hjemme")
    st.caption("Købte varer ryger automatisk herind. Tryk 'Brugt' og vælg om den skal på indkøbslisten igen.")

    # Prompt after "Brugt"
    if S.get("used_prompt"):
        nm = S["used_prompt"].get("name", "")
        st.markdown('<div class="k-card">', unsafe_allow_html=True)
        st.markdown(f'<div class="k-title">Brugt: {nm}</div>', unsafe_allow_html=True)
        st.markdown('<div class="k-muted">Tilføj til indkøbslisten igen?</div>', unsafe_allow_html=True)
        yes = st.button("✅ Ja, tilføj")
        no = st.button("❌ Nej")
        if yes:
            mem = S["memory"].get(key(nm), {})
            add_or_merge_shopping(
                nm,
                int(mem.get("default_qty", 1) or 1),
                mem.get("category", "Andet"),
                mem.get("store", "Netto"),
            )
            S["used_prompt"] = None
            persist()
            st.success("Tilføjet ✅")
            st.rerun()
        if no:
            S["used_prompt"] = None
            persist()
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    q = st.text_input("Søg i hjemme", placeholder="Søg…", key="home_search")

    home = list(S["home_items"])
    if q.strip():
        qq = q.strip().lower()
        home = [x for x in home if qq in (x.get("name", "").lower())]

    home.sort(key=lambda x: (x.get("location", ""), x.get("name", "").lower()))

    if not home:
        st.info("Ingen varer derhjemme endnu.")
    else:
        last_loc = None
        for it in home:
            loc = it.get("location", "Andet")
            if loc != last_loc:
                st.markdown(f"#### {loc}")
                last_loc = loc

            st.markdown('<div class="k-card">', unsafe_allow_html=True)
            st.markdown(f'<div class="k-title">{it.get("name","")} · {it.get("qty",1)}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="k-muted">{it.get("category","")} · Senest tilføjet: {human_time(it.get("added_at"))}</div>', unsafe_allow_html=True)

            if st.button("🍽️ Brugt", key=f"used_{it['id']}"):
                it["qty"] = max(0, int(it.get("qty", 1)) - 1)
                it["last_used_at"] = now_iso()
                if it["qty"] <= 0:
                    S["home_items"] = [x for x in S["home_items"] if x["id"] != it["id"]]
                persist()
                S["used_prompt"] = {"home_item_id": it["id"], "name": it.get("name", "")}
                persist()
                st.rerun()

            # Minimal edit: change location only (optional but useful)
            new_loc = st.selectbox("Placering", S["home_locations"], index=S["home_locations"].index(loc) if loc in S["home_locations"] else 0, key=f"loc_{it['id']}")
            if new_loc != loc:
                it["location"] = new_loc
                persist()
                st.rerun()

            st.markdown("</div>", unsafe_allow_html=True)

# -------------------------
# ⭐ STANDARD
# -------------------------
with tab_std:
    st.subheader("⭐ Standardvarer")
    st.caption("Sorteret efter kategori. Ét tryk for at tilføje til indkøb.")

    q = st.text_input("Søg i standardvarer", placeholder="Søg…", key="std_search")

    std = list(S["standard_items"])
    if q.strip():
        qq = q.strip().lower()
        std = [x for x in std if qq in (x.get("name", "").lower())]

    std.sort(key=lambda x: (x.get("category", ""), x.get("name", "").lower(), x.get("store", "")))

    if not std:
        st.info("Ingen standardvarer endnu.")
    else:
        last_cat = None
        for it in std:
            cat = it.get("category", "Andet")
            if cat != last_cat:
                st.markdown(f"#### {cat}")
                last_cat = cat

            st.markdown('<div class="k-card">', unsafe_allow_html=True)
            st.markdown(f'<div class="k-title">{it.get("name","")}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="k-muted">{it.get("store","")} · antal {it.get("default_qty",1)}</div>', unsafe_allow_html=True)

            if st.button("➕ Tilføj", key=f"stdadd_{it['id']}"):
                add_or_merge_shopping(it["name"], int(it.get("default_qty", 1)), it.get("category", "Andet"), it.get("store", "Netto"))
                upsert_memory(it["name"], it.get("category", "Andet"), it.get("store", "Netto"), int(it.get("default_qty", 1)), True)
                st.success("Tilføjet ✅")
                st.rerun()

            st.markdown("</div>", unsafe_allow_html=True)

# -------------------------
# ⚙️ SETTINGS (small)
# -------------------------
with tab_settings:
    st.subheader("⚙️")
    st.caption("Hold det simpelt. Tilpas standardplacering for købte varer.")

    settings = S["settings"]
    settings["default_home_location"] = st.selectbox(
        "Når noget købes, læg i Hjemme som…",
        S["home_locations"],
        index=S["home_locations"].index(settings.get("default_home_location", "Køleskab")) if settings.get("default_home_location", "Køleskab") in S["home_locations"] else 0,
    )
    S["settings"] = settings
    persist()

    st.caption(f"Sidst gemt: {S['meta'].get('last_saved') or '—'}")
