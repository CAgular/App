import json
import re
import uuid
from datetime import datetime, date, timedelta
from pathlib import Path

import streamlit as st
from src.config import APP_TITLE

# =========================
# Page config + navigation
# =========================
st.set_page_config(page_title=f"{APP_TITLE} • Shopping", page_icon="🛒", layout="centered")
st.link_button("⬅️ Tilbage til forside", "/")

st.title("🛒 Shopping")
st.caption("Mobil-venlig indkøbsliste med butikker, kategorier, favoritter og gentagelser.")

# =========================
# Mobile-first CSS
# =========================
st.markdown(
    """
    <style>
      /* Make inputs/buttons feel nicer on mobile */
      .stButton > button { width: 100%; padding: 0.65rem 0.9rem; border-radius: 14px; }
      .stDownloadButton > button { width: 100%; padding: 0.65rem 0.9rem; border-radius: 14px; }
      div[data-testid="stTextInput"] input, div[data-testid="stTextArea"] textarea,
      div[data-testid="stNumberInput"] input, div[data-testid="stSelectbox"] div {
        border-radius: 14px;
      }

      /* Reduce vertical gaps a bit */
      .block-container { padding-top: 1.0rem; padding-bottom: 2.0rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

# =========================
# Simple persistence (JSON)
# =========================
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
DATA_FILE = DATA_DIR / "shopping_list.json"

DEFAULT_STORES = ["Netto", "Rema 1000", "Føtex", "Lidl", "Apotek", "Bauhaus", "Andet"]
DEFAULT_CATEGORIES = [
    "Frugt & grønt", "Mejeri", "Brød", "Kød/fisk", "Kolonial", "Frost",
    "Drikke", "Husholdning", "Baby", "Toilet", "Rengøring", "DIY", "Andet",
]
DEFAULT_TAGS = ["Baby", "Madplan", "Hus", "Gæster", "Weekend", "Tilbud"]


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


def today_iso() -> str:
    return date.today().isoformat()


def safe_int(x, default=0) -> int:
    try:
        return int(x)
    except Exception:
        return default


def load_data() -> dict:
    if DATA_FILE.exists():
        try:
            return json.loads(DATA_FILE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_data(data: dict) -> None:
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def ensure_state():
    if "shopping" not in st.session_state:
        data = load_data() or {}
        st.session_state.shopping = {
            "items": data.get("items", []),
            "stores": data.get("stores", DEFAULT_STORES),
            "categories": data.get("categories", DEFAULT_CATEGORIES),
            "tags": data.get("tags", DEFAULT_TAGS),
            "settings": data.get(
                "settings",
                {
                    "default_store": "Netto",
                    "default_category": "Andet",
                    "hide_bought": True,
                    "store_filter": "Alle",
                    "sort_mode": "Butik → Kategori → Navn",
                },
            ),
            "meta": data.get("meta", {"last_saved": None}),
        }


def persist():
    payload = {
        "items": st.session_state.shopping["items"],
        "stores": st.session_state.shopping["stores"],
        "categories": st.session_state.shopping["categories"],
        "tags": st.session_state.shopping["tags"],
        "settings": st.session_state.shopping["settings"],
        "meta": {"last_saved": now_iso()},
    }
    save_data(payload)
    st.session_state.shopping["meta"]["last_saved"] = payload["meta"]["last_saved"]


ensure_state()


def normalize_item(it: dict) -> dict:
    item = dict(it)

    item.setdefault("id", str(uuid.uuid4()))
    item["name"] = (item.get("name") or "").strip()

    item["qty"] = max(1, safe_int(item.get("qty", 1), 1))
    item["unit"] = (item.get("unit") or "").strip()

    s = st.session_state.shopping["settings"]
    item.setdefault("store", s.get("default_store", "Netto"))
    item.setdefault("category", s.get("default_category", "Andet"))
    item.setdefault("tags", [])
    item["tags"] = list(item.get("tags") or [])

    item.setdefault("favorite", False)
    item.setdefault("note", "")

    item["repeat_days"] = max(0, safe_int(item.get("repeat_days", 0), 0))
    item.setdefault("last_bought", None)

    item.setdefault("status", "open")  # open/bought
    if item["status"] not in ("open", "bought"):
        item["status"] = "open"

    item.setdefault("created_at", now_iso())
    item.setdefault("bought_at", None)

    return item


def items():
    st.session_state.shopping["items"] = [normalize_item(x) for x in st.session_state.shopping["items"]]
    return st.session_state.shopping["items"]


def add_item(item: dict):
    item = normalize_item(item)
    st.session_state.shopping["items"].append(item)
    persist()


def update_item(item: dict):
    item = normalize_item(item)
    all_items = items()
    for i, it in enumerate(all_items):
        if it["id"] == item["id"]:
            all_items[i] = item
            st.session_state.shopping["items"] = all_items
            persist()
            return


def delete_item(item_id: str):
    st.session_state.shopping["items"] = [it for it in items() if it["id"] != item_id]
    persist()


def set_status(item_id: str, bought: bool):
    all_items = items()
    for it in all_items:
        if it["id"] == item_id:
            if bought:
                it["status"] = "bought"
                it["bought_at"] = now_iso()
                it["last_bought"] = today_iso()
            else:
                it["status"] = "open"
                it["bought_at"] = None
            break
    st.session_state.shopping["items"] = all_items
    persist()


def toggle_fav(item_id: str):
    all_items = items()
    for it in all_items:
        if it["id"] == item_id:
            it["favorite"] = not bool(it.get("favorite"))
            break
    st.session_state.shopping["items"] = all_items
    persist()


def compute_due(all_items: list[dict]) -> list[dict]:
    due = []
    today = date.today()
    for it in all_items:
        rd = safe_int(it.get("repeat_days", 0), 0)
        if rd <= 0:
            continue
        last = it.get("last_bought")
        if not last:
            due.append(it)
            continue
        try:
            lb = date.fromisoformat(last)
            if lb + timedelta(days=rd) <= today:
                due.append(it)
        except Exception:
            due.append(it)
    return due


def parse_quick(text: str) -> dict | None:
    """
    Supports:
      "Mælk"
      "Bananer x6"
      "Bleer 2"
      "Kaffe x2 (Baby, Madplan)"
    """
    t = (text or "").strip()
    if not t:
        return None

    tags = []
    m_tags = re.search(r"\((.*?)\)\s*$", t)
    if m_tags:
        tags = [x.strip() for x in m_tags.group(1).split(",") if x.strip()]
        t = t[: m_tags.start()].strip()

    qty = 1
    m_qty = re.search(r"(?:\s+x\s*|\s+)(\d+)\s*$", t, flags=re.IGNORECASE)
    if m_qty:
        qty = safe_int(m_qty.group(1), 1)
        t = t[: m_qty.start()].strip()

    if not t:
        return None

    s = st.session_state.shopping["settings"]
    return {
        "name": t,
        "qty": max(1, qty),
        "store": s.get("default_store", "Netto"),
        "category": s.get("default_category", "Andet"),
        "tags": tags,
        "status": "open",
    }


# =========================
# Mobile-friendly "top bar"
# =========================
s = st.session_state.shopping["settings"]
all_items = items()

# Quick add (always on top)
with st.form("quick_add", clear_on_submit=True):
    st.subheader("➕ Hurtig tilføj")
    q = st.text_input("Skriv en vare (fx “Mælk”, “Bananer x6”, “Bleer x1 (Baby)”)")
    submitted = st.form_submit_button("Tilføj til listen")
    if submitted:
        item = parse_quick(q)
        if not item:
            st.warning("Skriv et varenavn.")
        else:
            add_item(item)
            st.success("Tilføjet ✅")
            st.rerun()

# Filters compact (no columns)
st.subheader("🧾 Liste")

stores = ["Alle"] + st.session_state.shopping["stores"]

with st.expander("Filtre & visning", expanded=False):
    s["store_filter"] = st.selectbox("Butik-filter", stores, index=stores.index(s.get("store_filter", "Alle")) if s.get("store_filter", "Alle") in stores else 0)
    s["hide_bought"] = st.toggle("Skjul købte varer", value=bool(s.get("hide_bought", True)))
    s["sort_mode"] = st.selectbox(
        "Sortering",
        ["Butik → Kategori → Navn", "Kategori → Navn", "Navn", "Nyeste først"],
        index=["Butik → Kategori → Navn", "Kategori → Navn", "Navn", "Nyeste først"].index(s.get("sort_mode", "Butik → Kategori → Navn")),
    )
    s["default_store"] = st.selectbox("Standard butik (til hurtig tilføj)", st.session_state.shopping["stores"], index=st.session_state.shopping["stores"].index(s.get("default_store", "Netto")) if s.get("default_store") in st.session_state.shopping["stores"] else 0)
    s["default_category"] = st.selectbox("Standard kategori (til hurtig tilføj)", st.session_state.shopping["categories"], index=st.session_state.shopping["categories"].index(s.get("default_category", "Andet")) if s.get("default_category") in st.session_state.shopping["categories"] else 0)

    persist()

search = st.text_input("Søg", placeholder="Søg i varer…")

# Due recurring suggestions (mobile-friendly)
due = compute_due(all_items)
if due:
    with st.expander(f"🔁 Forslag (gentagelser klar): {len(due)}", expanded=False):
        st.caption("Tryk for at tilføje som nye åbne varer.")
        for it in sorted(due, key=lambda x: (x.get("store", ""), x.get("category", ""), x.get("name", "").lower())):
            if st.button(f"➕ {it['name']}  ·  {it.get('store','')} / {it.get('category','')}", key=f"due_{it['id']}"):
                add_item(
                    {
                        "name": it["name"],
                        "qty": it.get("qty", 1),
                        "unit": it.get("unit", ""),
                        "store": it.get("store", s.get("default_store", "Netto")),
                        "category": it.get("category", s.get("default_category", "Andet")),
                        "tags": it.get("tags", []),
                        "note": it.get("note", ""),
                        "favorite": it.get("favorite", False),
                        "repeat_days": it.get("repeat_days", 0),
                        "status": "open",
                    }
                )
                st.rerun()

# Apply filters
filtered = all_items[:]

if s.get("hide_bought", True):
    filtered = [it for it in filtered if it["status"] == "open"]

if s.get("store_filter", "Alle") != "Alle":
    filtered = [it for it in filtered if it.get("store") == s["store_filter"]]

if search.strip():
    q = search.strip().lower()
    filtered = [it for it in filtered if q in it.get("name", "").lower() or q in (it.get("note") or "").lower()]

# Sorting
sort_mode = s.get("sort_mode", "Butik → Kategori → Navn")

def sort_key(it: dict):
    if sort_mode == "Nyeste først":
        return -int(datetime.fromisoformat(it.get("created_at", now_iso())).timestamp())
    if sort_mode == "Navn":
        return it.get("name", "").lower()
    if sort_mode == "Kategori → Navn":
        return (it.get("category", ""), it.get("name", "").lower())
    return (it.get("store", ""), it.get("category", ""), it.get("name", "").lower())

filtered.sort(key=sort_key)

# =========================
# List rendering (mobile-first)
# =========================
if not filtered:
    st.info("Ingen varer matcher lige nu.")
else:
    last_group = None
    for it in filtered:
        group = ""
        if sort_mode == "Butik → Kategori → Navn":
            group = f"{it.get('store','')} · {it.get('category','')}"
        elif sort_mode == "Kategori → Navn":
            group = it.get("category", "Andet")

        if group and group != last_group:
            st.markdown(f"#### {group}")
            last_group = group

        # BIG touch-friendly row, with extra actions tucked away
        with st.container(border=True):
            bought = (it["status"] == "bought")
            label = it["name"]
            if it.get("qty", 1) != 1 or it.get("unit"):
                label += f"  ·  {it.get('qty',1)} {it.get('unit','')}".strip()

            new_val = st.checkbox(label, value=bought, key=f"chk_{it['id']}")
            if new_val != bought:
                set_status(it["id"], new_val)
                st.rerun()

            meta = []
            if it.get("tags"):
                meta.append("🏷️ " + ", ".join(it["tags"]))
            if it.get("note"):
                meta.append("📝 " + it["note"])
            if meta:
                st.caption(" · ".join(meta))

            with st.expander("Flere muligheder", expanded=False):
                # Favorit toggle as a big button
                if st.button("⭐ Fjern favorit" if it.get("favorite") else "☆ Gør til favorit", key=f"fav_{it['id']}"):
                    toggle_fav(it["id"])
                    st.rerun()

                # Edit form (one column, mobile)
                with st.form(f"edit_{it['id']}"):
                    name = st.text_input("Navn", value=it["name"])
                    qty = st.number_input("Antal", min_value=1, value=int(it.get("qty", 1)), step=1)
                    unit = st.text_input("Enhed (valgfri)", value=it.get("unit", ""))

                    store = st.selectbox("Butik", st.session_state.shopping["stores"],
                                         index=st.session_state.shopping["stores"].index(it.get("store")) if it.get("store") in st.session_state.shopping["stores"] else 0)
                    category = st.selectbox("Kategori", st.session_state.shopping["categories"],
                                            index=st.session_state.shopping["categories"].index(it.get("category")) if it.get("category") in st.session_state.shopping["categories"] else 0)
                    tags_sel = st.multiselect("Tags", st.session_state.shopping["tags"], default=it.get("tags") or [])
                    repeat_days = st.number_input("Gentag hver X dag(e) (0=off)", min_value=0, value=int(it.get("repeat_days", 0)), step=1)
                    note = st.text_input("Note", value=it.get("note", ""))

                    save = st.form_submit_button("💾 Gem ændringer")
                    if save:
                        it["name"] = name.strip()
                        it["qty"] = int(qty)
                        it["unit"] = unit.strip()
                        it["store"] = store
                        it["category"] = category
                        it["tags"] = tags_sel
                        it["repeat_days"] = int(repeat_days)
                        it["note"] = note.strip()
                        update_item(it)
                        st.success("Gemt ✅")
                        st.rerun()

                if st.button("🗑️ Slet vare", key=f"del_{it['id']}"):
                    delete_item(it["id"])
                    st.rerun()

# =========================
# Favorites as a mobile section
# =========================
with st.expander("⭐ Favoritter (køb igen hurtigt)", expanded=False):
    favs = [it for it in all_items if it.get("favorite")]
    if not favs:
        st.caption("Ingen favoritter endnu. Markér en vare som favorit inde i “Flere muligheder”.")
    else:
        favs.sort(key=lambda x: (x.get("store", ""), x.get("category", ""), x.get("name", "").lower()))
        for it in favs:
            if st.button(f"➕ {it['name']}  ·  {it.get('store','')} / {it.get('category','')}", key=f"fav_add_{it['id']}"):
                add_item(
                    {
                        "name": it["name"],
                        "qty": it.get("qty", 1),
                        "unit": it.get("unit", ""),
                        "store": it.get("store", s.get("default_store", "Netto")),
                        "category": it.get("category", s.get("default_category", "Andet")),
                        "tags": it.get("tags", []),
                        "note": it.get("note", ""),
                        "favorite": True,
                        "repeat_days": it.get("repeat_days", 0),
                        "status": "open",
                    }
                )
                st.rerun()

st.divider()

# =========================
# Bottom utilities (mobile)
# =========================
if st.button("🧹 Ryd købte varer"):
    st.session_state.shopping["items"] = [it for it in items() if it["status"] != "bought"]
    persist()
    st.rerun()

export_blob = json.dumps(
    {
        "items": st.session_state.shopping["items"],
        "stores": st.session_state.shopping["stores"],
        "categories": st.session_state.shopping["categories"],
        "tags": st.session_state.shopping["tags"],
        "settings": st.session_state.shopping["settings"],
        "meta": st.session_state.shopping["meta"],
    },
    ensure_ascii=False,
    indent=2,
)
st.download_button("⬇️ Eksportér (JSON)", data=export_blob, file_name="shopping_export.json", mime="application/json")
st.caption(f"Sidst gemt: {st.session_state.shopping['meta'].get('last_saved') or '—'}")
