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


def delete_open_item(item_id: str):
    S["shopping_items"] = [x for x in S["shopping_items"] if x["id"] != item_id]
    persist()


# =========================================================
# Form state keys (to avoid "every other time" bugs)
# =========================================================
K_NAME = "add_name"
K_CAT = "add_category"
K_STORE = "add_store"
K_QTY = "add_qty"
K_STD = "add_standard"
K_LAST_AUTOFILL = "last_autofill_name"

# initialize defaults (once)
if K_NAME not in st.session_state:
    st.session_state[K_NAME] = ""
if K_CAT not in st.session_state:
    st.session_state[K_CAT] = "Andet"
if K_STORE not in st.session_state:
    st.session_state[K_STORE] = S["settings"].get("default_store", "Netto")
if K_QTY not in st.session_state:
    st.session_state[K_QTY] = 1
if K_STD not in st.session_state:
    st.session_state[K_STD] = False
if K_LAST_AUTOFILL not in st.session_state:
    st.session_state[K_LAST_AUTOFILL] = ""


def maybe_autofill_from_memory():
    nm = normalize_name(st.session_state.get(K_NAME, ""))
    if not nm:
        return
    mk = key(nm)
    mem = S["memory"].get(mk)
    # only autofill when the typed name changed (prevents overwriting user choices)
    if mem and st.session_state.get(K_LAST_AUTOFILL, "") != mk:
        st.session_state[K_CAT] = mem.get("category", st.session_state[K_CAT])
        st.session_state[K_STORE] = mem.get("store", st.session_state[K_STORE])
        st.session_state[K_STD] = bool(mem.get("is_standard", st.session_state[K_STD]))
        # qty: optional – we keep it, but it can be convenient:
        st.session_state[K_QTY] = int(mem.get("default_qty", st.session_state[K_QTY]) or 1)
        st.session_state[K_LAST_AUTOFILL] = mk


# =========================================================
# Tabs
# =========================================================
tab_shop, tab_home, tab_std, tab_settings = st.tabs(["🧾 Indkøb", "🏠 Hjemme", "⭐ Standard", "⚙️ Indstillinger"])

# -------------------------
# 🧾 INDKØB
# -------------------------
with tab_shop:
    st.subheader("➕ Tilføj")

    # run autofill on each render (safe)
    maybe_autofill_from_memory()

    with st.form("add_item_form"):
        st.text_input("Vare", placeholder="Skriv fx: bananer", key=K_NAME)

        st.selectbox("Kategori", S["categories"], key=K_CAT)
        st.selectbox("Butik", S["stores"], key=K_STORE)
        st.number_input("Antal", min_value=1, step=1, key=K_QTY)
        st.checkbox("⭐ Standardvare", key=K_STD)

        submit = st.form_submit_button("✅ Tilføj til indkøbslisten")

    if submit:
        name = normalize_name(st.session_state[K_NAME])
        if not name:
            st.warning("Skriv et varenavn.")
        else:
            category = st.session_state[K_CAT]
            store = st.session_state[K_STORE]
            qty = int(st.session_state[K_QTY] or 1)
            is_standard = bool(st.session_state[K_STD])

            add_or_merge_shopping(name, qty, category, store)
            upsert_memory(name, category, store, qty, is_standard)
            if is_standard:
                add_or_update_standard(name, qty, category, store)

            # reset fields exactly as you asked:
            st.session_state[K_NAME] = ""
            st.session_state[K_QTY] = 1
            st.session_state[K_STD] = False
            st.session_state[K_LAST_AUTOFILL] = ""
            # keep user's chosen category/store for speed (optional). If you want reset too:
            # st.session_state[K_CAT] = "Andet"
            # st.session_state[K_STORE] = S["settings"].get("default_store","Netto")

            st.success("Tilføjet ✅")
            st.rerun()

    with st.expander("✨ Forslag (fra historik)", expanded=False):
        pref = st.text_input("Skriv start (fx 'ban')", key="pref_sug")
        for sug in suggestions(pref, limit=12):
            label = f"{sug.get('name','')} (antal {sug.get('default_qty',1)})"
            if st.button(label, key=f"sug_{key(sug.get('name',''))}_{sug.get('store','')}_{sug.get('category','')}"):
                # load suggestion into form fields (better UX end bare at tilføje direkte)
                st.session_state[K_NAME] = sug.get("name", "")
                st.session_state[K_CAT] = sug.get("category", "Andet")
                st.session_state[K_STORE] = sug.get("store", S["settings"].get("default_store", "Netto"))
                st.session_state[K_QTY] = int(sug.get("default_qty", 1) or 1)
                st.session_state[K_STD] = bool(sug.get("is_standard", False))
                st.session_state[K_LAST_AUTOFILL] = key(sug.get("name", ""))
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

            # One compact row: name | - | qty | + | KØBT (big) | delete (small)
            c_name, c_minus, c_qty, c_plus, c_buy, c_del = st.columns(
                [5.6, 1.05, 1.05, 1.05, 2.4, 1.0], vertical_alignment="center"
            )

            with c_name:
                st.markdown(f'<div class="k-title">{it.get("name","")}</div>', unsafe_allow_html=True)

            with c_minus:
                st.markdown('<div class="k-smallbtn">', unsafe_allow_html=True)
                if st.button("➖", key=f"m_{it['id']}"):
                    change_qty(it["id"], -1)
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

            with c_qty:
                st.markdown(
                    f"<div class='k-muted' style='text-align:center; font-weight:800;'>{it.get('qty',1)}</div>",
                    unsafe_allow_html=True,
                )

            with c_plus:
                st.markdown('<div class="k-smallbtn">', unsafe_allow_html=True)
                if st.button("➕", key=f"p_{it['id']}"):
                    change_qty(it["id"], +1)
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

            with c_buy:
                if st.button("✅ Købt", key=f"buy_{it['id']}"):
                    mark_bought(it["id"])
                    st.rerun()

            with c_del:
                st.markdown('<div class="k-smallbtn">', unsafe_allow_html=True)
                if st.button("🗑️", key=f"d_{it['id']}"):
                    delete_open_item(it["id"])
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

            st.markdown("</div>", unsafe_allow_html=True)

    if settings.get("show_bought", False):
        with st.expander(f"✅ Købte varer ({len(bought_items)})", expanded=False):
            if not bought_items:
                st.caption("Ingen købte varer.")
            else:
                for it in bought_items[:100]:
                    st.markdown('<div class="k-card">', unsafe_allow_html=True)
                    st.markdown(
                        f'<div class="k-title">{it.get("name","")} · {it.get("qty",1)}</div>',
                        unsafe_allow_html=True,
                    )
                    st.markdown(
                        f'<div class="k-muted">Købt: {human_time(it.get("bought_at"))}</div>',
                        unsafe_allow_html=True,
                    )
                    st.markdown("</div>", unsafe_allow_html=True)

# -------------------------
# 🏠 HJEMME
# -------------------------
with tab_home:
    st.subheader("🏠 Hjemme")
    st.caption("Købte varer bliver automatisk lagt her (default placering vælges i Indstillinger).")

    if S.get("used_prompt"):
        nm = S["used_prompt"].get("name", "")
        st.markdown('<div class="k-card">', unsafe_allow_html=True)
        st.markdown(f'<div class="k-title">Brugt: {nm}</div>', unsafe_allow_html=True)
        st.markdown('<div class="k-muted">Tilføj til indkøbslisten igen?</div>', unsafe_allow_html=True)
        yes, no = st.columns([2, 1], vertical_alignment="center")
        with yes:
            if st.button("✅ Ja, tilføj"):
                mem = S["memory"].get(key(nm), {})
                add_or_merge_shopping(
                    nm,
                    int(mem.get("default_qty", 1) or 1),
                    mem.get("category", "Andet"),
                    mem.get("store", S["settings"].get("default_store", "Netto")),
                )
                S["used_prompt"] = None
                persist()
                st.success("Tilføjet ✅")
                st.rerun()
        with no:
            if st.button("❌ Nej"):
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
            c1, c2, c3 = st.columns([5.5, 1.2, 2.3], vertical_alignment="center")
            with c1:
                st.markdown(f'<div class="k-title">{it.get("name","")}</div>', unsafe_allow_html=True)
                st.markdown(f'<div class="k-muted">Antal: {it.get("qty",1)}</div>', unsafe_allow_html=True)

            with c2:
                st.markdown('<div class="k-smallbtn">', unsafe_allow_html=True)
                if st.button("🍽️", key=f"used_{it['id']}"):
                    it["qty"] = max(0, int(it.get("qty", 1)) - 1)
                    it["last_used_at"] = now_iso()
                    if it["qty"] <= 0:
                        S["home_items"] = [x for x in S["home_items"] if x["id"] != it["id"]]
                    persist()
                    S["used_prompt"] = {"home_item_id": it["id"], "name": it.get("name", "")}
                    persist()
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

            with c3:
                new_loc = st.selectbox(
                    "Placering",
                    S["home_locations"],
                    index=S["home_locations"].index(loc) if loc in S["home_locations"] else 0,
                    key=f"hloc_{it['id']}",
                )
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
    st.caption("Sorteret efter kategori. Tryk ➕ for at tilføje til indkøb.")

    q = st.text_input("Søg i standardvarer", placeholder="Søg…", key="std_search")

    std = list(S["standard_items"])
    if q.strip():
        qq = q.strip().lower()
        std = [x for x in std if qq in (x.get("name", "").lower())]

    std.sort(key=lambda x: (x.get("category", ""), x.get("name", "").lower(), x.get("store", "")))

    if not std:
        st.info("Ingen standardvarer endnu. Kryds “Standardvare” af når du tilføjer en vare.")
    else:
        last_cat = None
        for it in std:
            cat = it.get("category", "Andet")
            if cat != last_cat:
                st.markdown(f"#### {cat}")
                last_cat = cat

            st.markdown('<div class="k-card">', unsafe_allow_html=True)
            c1, c2, c3 = st.columns([6, 1.4, 2.6], vertical_alignment="center")
            with c1:
                st.markdown(f'<div class="k-title">{it.get("name","")}</div>', unsafe_allow_html=True)
            with c2:
                st.markdown(
                    f"<div class='k-muted' style='text-align:center; font-weight:800;'>{it.get('default_qty',1)}</div>",
                    unsafe_allow_html=True,
                )
            with c3:
                if st.button("➕ Tilføj", key=f"stdadd_{it['id']}"):
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
                    st.success("Tilføjet ✅")
                    st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)

# -------------------------
# ⚙️ INDSTILLINGER
# -------------------------
with tab_settings:
    st.subheader("⚙️ Indstillinger")
    st.caption("Her kan du ændre defaults og tilføje butikker/kategorier/placeringer.")

    settings = S["settings"]

    settings["default_store"] = st.selectbox(
        "Default butik (når du tilføjer nye varer)",
        S["stores"],
        index=S["stores"].index(settings.get("default_store", "Netto")) if settings.get("default_store", "Netto") in S["stores"] else 0,
        key="set_default_store",
    )

    settings["default_home_location"] = st.selectbox(
        "Når noget købes: læg i Hjemme som…",
        S["home_locations"],
        index=S["home_locations"].index(settings.get("default_home_location", "Køleskab")) if settings.get("default_home_location", "Køleskab") in S["home_locations"] else 0,
        key="set_default_home",
    )

    S["settings"] = settings
    persist()

    st.divider()
    st.subheader("➕ Tilføj til lister")

    with st.expander("Butikker", expanded=False):
        new_store = st.text_input("Ny butik", placeholder="Fx Meny", key="new_store")
        if st.button("Tilføj butik", key="btn_add_store"):
            ns = (new_store or "").strip()
            if ns and ns not in S["stores"]:
                S["stores"].append(ns)
                persist()
                st.success("Tilføjet ✅")
                st.rerun()
        st.caption(" • " + " • ".join(S["stores"]))

    with st.expander("Kategorier", expanded=False):
        new_cat = st.text_input("Ny kategori", placeholder="Fx Snacks", key="new_cat")
        if st.button("Tilføj kategori", key="btn_add_cat"):
            nc = (new_cat or "").strip()
            if nc and nc not in S["categories"]:
                S["categories"].append(nc)
                persist()
                st.success("Tilføjet ✅")
                st.rerun()
        st.caption(" • " + " • ".join(S["categories"]))

    with st.expander("Steder i hjemmet", expanded=False):
        new_loc = st.text_input("Nyt sted", placeholder="Fx Skur", key="new_loc")
        if st.button("Tilføj sted", key="btn_add_loc"):
            nl = (new_loc or "").strip()
            if nl and nl not in S["home_locations"]:
