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
st.caption("iPhone-venlig indkøbsliste med standardvarer, historik og 'hjemme'-lager.")

# =========================================================
# Modern, mobile-first styling
# =========================================================
st.markdown(
    """
    <style>
      .block-container { padding-top: 1.0rem; padding-bottom: 2.0rem; max-width: 720px; }
      .stButton>button, .stDownloadButton>button {
        width: 100%;
        padding: 0.72rem 0.95rem;
        border-radius: 16px;
        font-weight: 600;
      }
      div[data-testid="stTextInput"] input,
      div[data-testid="stNumberInput"] input,
      div[data-testid="stSelectbox"] div,
      div[data-testid="stMultiSelect"] div,
      div[data-testid="stTextArea"] textarea {
        border-radius: 16px !important;
      }
      /* Make checkboxes easier to tap */
      label[data-testid="stCheckbox"] { padding: 0.35rem 0; }
      /* Card feel */
      .k-card {
        border: 1px solid rgba(49, 51, 63, 0.15);
        border-radius: 18px;
        padding: 0.85rem 0.9rem;
        margin: 0.55rem 0;
        background: rgba(255,255,255,0.03);
      }
      .k-muted { opacity: 0.75; font-size: 0.92rem; }
      .k-title { font-weight: 700; font-size: 1.05rem; margin-bottom: 0.15rem; }
      .k-pill {
        display: inline-block; padding: 0.12rem 0.55rem;
        border-radius: 999px; border: 1px solid rgba(49, 51, 63, 0.18);
        margin-right: 0.35rem; margin-top: 0.25rem;
        font-size: 0.85rem; opacity: 0.85;
      }
      .k-spacer { height: 0.25rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

# =========================================================
# Persistence
# =========================================================
DATA_DIR = Path("data")
DATA_DIR.mkdir(exist_ok=True)
DATA_FILE = DATA_DIR / "shopping_v2.json"

DEFAULT_STORES = ["Netto", "Rema 1000", "Føtex", "Lidl", "Apotek", "Bauhaus", "Andet"]
DEFAULT_CATEGORIES = [
    "Frugt & grønt",
    "Pålæg",
    "Mejeri",
    "Kød",
    "Fisk",
    "Brød",
    "Kolonial",
    "Frost",
    "Drikke",
    "Baby",
    "Husholdning",
    "Rengøring",
    "Toilet",
    "DIY",
    "Andet",
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
    if "shopping_v2" in st.session_state:
        return

    data = load_data() or {}

    st.session_state.shopping_v2 = {
        # Shopping list items (open + bought in same list via status)
        # item: {id, name, qty, category, store, status, created_at, bought_at}
        "shopping_items": data.get("shopping_items", []),

        # Standard items (templates)
        # standard: {id, name, default_qty, category, store, created_at}
        "standard_items": data.get("standard_items", []),

        # Home inventory
        # home: {id, name, qty, location, category, store, added_at, last_used_at}
        "home_items": data.get("home_items", []),

        # Memory: remembered items by name (lower)
        # mem[name] = {category, store, default_qty, is_standard}
        "memory": data.get("memory", {}),

        "stores": data.get("stores", DEFAULT_STORES),
        "categories": data.get("categories", DEFAULT_CATEGORIES),
        "home_locations": data.get("home_locations", DEFAULT_HOME_LOCATIONS),

        "settings": data.get(
            "settings",
            {
                "hide_bought": True,
                "store_filter": "Alle",
                "default_home_location": "Køleskab",
                "group_mode": "Butik → Kategori",
            },
        ),
        "meta": data.get("meta", {"last_saved": None}),
        # UI helper
        "draft_from_suggestion": data.get("draft_from_suggestion", None),
        "used_prompt": None,  # {home_item_id, name}
    }


def persist():
    payload = {
        "shopping_items": st.session_state.shopping_v2["shopping_items"],
        "standard_items": st.session_state.shopping_v2["standard_items"],
        "home_items": st.session_state.shopping_v2["home_items"],
        "memory": st.session_state.shopping_v2["memory"],
        "stores": st.session_state.shopping_v2["stores"],
        "categories": st.session_state.shopping_v2["categories"],
        "home_locations": st.session_state.shopping_v2["home_locations"],
        "settings": st.session_state.shopping_v2["settings"],
        "draft_from_suggestion": st.session_state.shopping_v2.get("draft_from_suggestion"),
        "meta": {"last_saved": now_iso()},
    }
    save_data(payload)
    st.session_state.shopping_v2["meta"]["last_saved"] = payload["meta"]["last_saved"]


ensure_state()
S = st.session_state.shopping_v2


# =========================================================
# Core helpers
# =========================================================
def normalize_name(name: str) -> str:
    return (name or "").strip()


def mem_key(name: str) -> str:
    return normalize_name(name).lower()


def ensure_item_ids(items: List[Dict]) -> List[Dict]:
    out = []
    for it in items:
        d = dict(it)
        d.setdefault("id", str(uuid.uuid4()))
        out.append(d)
    return out


S["shopping_items"] = ensure_item_ids(S["shopping_items"])
S["standard_items"] = ensure_item_ids(S["standard_items"])
S["home_items"] = ensure_item_ids(S["home_items"])


def upsert_memory(name: str, category: str, store: str, default_qty: int, is_standard: bool):
    k = mem_key(name)
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


def find_memory_suggestions(prefix: str, limit: int = 6) -> List[Dict]:
    p = (prefix or "").strip().lower()
    if not p:
        return []
    hits = []
    for k, v in S["memory"].items():
        nm = (v.get("name") or "").strip()
        if nm.lower().startswith(p):
            hits.append(v)
    # sort: shortest first, then updated_at desc
    hits.sort(key=lambda x: (len(x.get("name", "")), x.get("updated_at", "")), reverse=False)
    return hits[:limit]


def add_to_shopping(name: str, qty: int, category: str, store: str):
    """If already exists as open item with same name+store+category, increase qty."""
    name = normalize_name(name)
    if not name:
        return

    qty = max(1, int(qty))
    # merge with existing open item
    for it in S["shopping_items"]:
        if (
            it.get("status", "open") == "open"
            and mem_key(it.get("name", "")) == mem_key(name)
            and it.get("store") == store
            and it.get("category") == category
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
    """Standard list is unique by name+category+store (case-insensitive name)."""
    name = normalize_name(name)
    if not name:
        return
    for st_it in S["standard_items"]:
        if (
            mem_key(st_it.get("name", "")) == mem_key(name)
            and st_it.get("category") == category
            and st_it.get("store") == store
        ):
            st_it["default_qty"] = max(1, int(default_qty))
            persist()
            return

    S["standard_items"].append(
        {
            "id": str(uuid.uuid4()),
            "name": name,
            "default_qty": max(1, int(default_qty)),
            "category": category,
            "store": store,
            "created_at": now_iso(),
        }
    )
    persist()


def add_to_home_from_purchase(name: str, qty: int, location: str, category: str, store: str):
    """Merge home inventory by name+location."""
    name = normalize_name(name)
    if not name:
        return
    qty = max(1, int(qty))
    for h in S["home_items"]:
        if mem_key(h.get("name", "")) == mem_key(name) and h.get("location") == location:
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
    """Mark shopping item bought, timestamp, and add to home automatically."""
    default_loc = S["settings"].get("default_home_location", "Køleskab")
    for it in S["shopping_items"]:
        if it["id"] == item_id and it.get("status") == "open":
            it["status"] = "bought"
            it["bought_at"] = now_iso()
            persist()
            add_to_home_from_purchase(
                name=it["name"],
                qty=int(it.get("qty", 1)),
                location=default_loc,
                category=it.get("category", "Andet"),
                store=it.get("store", "Andet"),
            )
            return


def mark_unbought(item_id: str):
    for it in S["shopping_items"]:
        if it["id"] == item_id:
            it["status"] = "open"
            it["bought_at"] = None
            persist()
            return


def delete_shopping_item(item_id: str):
    S["shopping_items"] = [x for x in S["shopping_items"] if x["id"] != item_id]
    persist()


def delete_standard_item(item_id: str):
    S["standard_items"] = [x for x in S["standard_items"] if x["id"] != item_id]
    persist()


def delete_home_item(item_id: str):
    S["home_items"] = [x for x in S["home_items"] if x["id"] != item_id]
    persist()


# =========================================================
# Tabs
# =========================================================
tab_shop, tab_home, tab_standard, tab_settings = st.tabs(["🧾 Indkøb", "🏠 Hjemme", "⭐ Standardvarer", "⚙️ Indstillinger"])


# =========================================================
# 🧾 INDKØB: input + liste + købte
# =========================================================
with tab_shop:
    # ---------- Add box (single, tight, mobile-friendly) ----------
    st.subheader("➕ Tilføj vare")

    # Draft prefill from suggestion (if user tapped a suggestion)
    draft = S.get("draft_from_suggestion") or {}
    draft_name = draft.get("name", "")

    name = st.text_input("Vare", value=draft_name, placeholder="Skriv fx: bananer, mælk, rugbrød…")

    # Suggestions while typing (memory)
    suggestions = find_memory_suggestions(name, limit=6) if name else []
    if suggestions:
        st.markdown('<div class="k-muted">Forslag (tryk for at udfylde):</div>', unsafe_allow_html=True)
        for sug in suggestions:
            label = f"{sug.get('name','')}  ·  {sug.get('store','')} / {sug.get('category','')}"
            if st.button(f"✨ {label}", key=f"sug_{mem_key(sug.get('name',''))}_{sug.get('store','')}_{sug.get('category','')}"):
                S["draft_from_suggestion"] = {
                    "name": sug.get("name", ""),
                    "category": sug.get("category", "Andet"),
                    "store": sug.get("store", "Andet"),
                    "qty": int(sug.get("default_qty", 1) or 1),
                    "is_standard": bool(sug.get("is_standard", False)),
                }
                persist()
                st.rerun()

    # Determine defaults from memory if exact match
    k = mem_key(name)
    mem = S["memory"].get(k) if k else None

    # Use either draft, memory, or fallbacks
    default_category = (S.get("draft_from_suggestion") or {}).get("category") or (mem.get("category") if mem else "Andet")
    default_store = (S.get("draft_from_suggestion") or {}).get("store") or (mem.get("store") if mem else "Netto")
    default_qty = (S.get("draft_from_suggestion") or {}).get("qty") or int(mem.get("default_qty", 1) if mem else 1)
    default_standard = (S.get("draft_from_suggestion") or {}).get("is_standard") or bool(mem.get("is_standard", False) if mem else False)

    category = st.selectbox("Kategori", S["categories"], index=S["categories"].index(default_category) if default_category in S["categories"] else S["categories"].index("Andet") if "Andet" in S["categories"] else 0)
    store = st.selectbox("Butik", S["stores"], index=S["stores"].index(default_store) if default_store in S["stores"] else 0)
    qty = st.number_input("Antal", min_value=1, value=max(1, int(default_qty)), step=1)

    is_standard = st.checkbox("⭐ Standardvare (gem i standardlisten)", value=bool(default_standard))

    # Add buttons
    add_btn = st.button("✅ Tilføj til indkøbslisten")
    if add_btn:
        clean = normalize_name(name)
        if not clean:
            st.warning("Skriv et varenavn.")
        else:
            add_to_shopping(clean, int(qty), category, store)
            # memory
            upsert_memory(clean, category, store, int(qty), is_standard)
            # standard list
            if is_standard:
                add_or_update_standard(clean, int(qty), category, store)

            # clear draft
            S["draft_from_suggestion"] = None
            persist()
            st.success("Tilføjet ✅")
            st.rerun()

    st.divider()

    # ---------- Filters (compact in expander) ----------
    settings = S["settings"]
    with st.expander("Filtre & visning", expanded=False):
        stores = ["Alle"] + S["stores"]
        settings["store_filter"] = st.selectbox(
            "Butik-filter",
            stores,
            index=stores.index(settings.get("store_filter", "Alle")) if settings.get("store_filter", "Alle") in stores else 0,
        )
        settings["hide_bought"] = st.toggle("Skjul købte varer", value=bool(settings.get("hide_bought", True)))
        settings["group_mode"] = st.selectbox("Gruppering", ["Butik → Kategori", "Kategori", "Ingen"], index=["Butik → Kategori", "Kategori", "Ingen"].index(settings.get("group_mode", "Butik → Kategori")))
        settings["default_home_location"] = st.selectbox(
            "Når noget købes: læg i “Hjemme” som…",
            S["home_locations"],
            index=S["home_locations"].index(settings.get("default_home_location", "Køleskab")) if settings.get("default_home_location", "Køleskab") in S["home_locations"] else 0,
        )
        S["settings"] = settings
        persist()

    search = st.text_input("Søg i indkøb", placeholder="Søg…")

    # ---------- Build shopping views ----------
    all_shop = list(S["shopping_items"])
    if settings.get("store_filter", "Alle") != "Alle":
        all_shop = [x for x in all_shop if x.get("store") == settings["store_filter"]]
    if search.strip():
        q = search.strip().lower()
        all_shop = [x for x in all_shop if q in (x.get("name", "").lower())]

    open_items = [x for x in all_shop if x.get("status") == "open"]
    bought_items = [x for x in all_shop if x.get("status") == "bought"]

    # Sort
    open_items.sort(key=lambda x: (x.get("store", ""), x.get("category", ""), x.get("name", "").lower()))
    bought_items.sort(key=lambda x: (x.get("bought_at") or "", x.get("name", "").lower()), reverse=True)

    # ---------- OPEN LIST ----------
    st.subheader("🧾 Indkøbsliste")

    if not open_items:
        st.info("Ingen åbne varer lige nu.")
    else:
        last_group = None
        for it in open_items:
            group_mode = settings.get("group_mode", "Butik → Kategori")
            group = None
            if group_mode == "Butik → Kategori":
                group = f"{it.get('store','')} · {it.get('category','')}"
            elif group_mode == "Kategori":
                group = f"{it.get('category','')}"
            else:
                group = None

            if group and group != last_group:
                st.markdown(f"#### {group}")
                last_group = group

            # Mobile card
            st.markdown('<div class="k-card">', unsafe_allow_html=True)
            title = f"{it.get('name','')} · {it.get('qty',1)}"
            st.markdown(f'<div class="k-title">{title}</div>', unsafe_allow_html=True)
            st.markdown(
                f'<div class="k-muted">{it.get("store","")} · {it.get("category","")}</div>',
                unsafe_allow_html=True,
            )

            bought = st.checkbox("Købt", value=False, key=f"buy_{it['id']}")
            if bought:
                mark_bought(it["id"])
                st.rerun()

            with st.expander("Flere muligheder", expanded=False):
                # Quick edits (mobile, simple)
                new_qty = st.number_input("Antal", min_value=1, value=int(it.get("qty", 1)), step=1, key=f"qty_{it['id']}")
                new_store = st.selectbox("Butik", S["stores"], index=S["stores"].index(it.get("store")) if it.get("store") in S["stores"] else 0, key=f"st_{it['id']}")
                new_cat = st.selectbox("Kategori", S["categories"], index=S["categories"].index(it.get("category")) if it.get("category") in S["categories"] else 0, key=f"cat_{it['id']}")
                mk_std = st.checkbox("⭐ Gem/Opdatér som standardvare", value=False, key=f"mkstd_{it['id']}")
                if st.button("💾 Gem ændringer", key=f"save_{it['id']}"):
                    it["qty"] = int(new_qty)
                    it["store"] = new_store
                    it["category"] = new_cat
                    persist()
                    # update memory
                    upsert_memory(it["name"], new_cat, new_store, int(new_qty), mk_std)
                    if mk_std:
                        add_or_update_standard(it["name"], int(new_qty), new_cat, new_store)
                    st.success("Gemt ✅")
                    st.rerun()

                if st.button("🗑️ Slet fra liste", key=f"del_{it['id']}"):
                    delete_shopping_item(it["id"])
                    st.rerun()

            st.markdown("</div>", unsafe_allow_html=True)

    # ---------- BOUGHT LIST ----------
    if not settings.get("hide_bought", True):
        st.subheader("✅ Købte varer")
        if not bought_items:
            st.caption("Ingen købte varer.")
        else:
            for it in bought_items[:60]:
                st.markdown('<div class="k-card">', unsafe_allow_html=True)
                st.markdown(
                    f'<div class="k-title">{it.get("name","")} · {it.get("qty",1)}</div>',
                    unsafe_allow_html=True,
                )
                st.markdown(
                    f'<div class="k-muted">Købt: {human_time(it.get("bought_at"))} · {it.get("store","")} · {it.get("category","")}</div>',
                    unsafe_allow_html=True,
                )
                if st.button("↩️ Fortryd (tilbage til åben)", key=f"undo_{it['id']}"):
                    mark_unbought(it["id"])
                    st.rerun()
                st.markdown("</div>", unsafe_allow_html=True)

    st.divider()
    # Utilities
    if st.button("🧹 Ryd købte varer (slet historik)"):
        S["shopping_items"] = [x for x in S["shopping_items"] if x.get("status") != "bought"]
        persist()
        st.rerun()

    export_blob = json.dumps(
        {
            "shopping_items": S["shopping_items"],
            "standard_items": S["standard_items"],
            "home_items": S["home_items"],
            "memory": S["memory"],
            "stores": S["stores"],
            "categories": S["categories"],
            "home_locations": S["home_locations"],
            "settings": S["settings"],
            "meta": S["meta"],
        },
        ensure_ascii=False,
        indent=2,
    )
    st.download_button("⬇️ Eksportér (JSON backup)", data=export_blob, file_name="shopping_v2_export.json", mime="application/json")
    st.caption(f"Sidst gemt: {S['meta'].get('last_saved') or '—'}")


# =========================================================
# 🏠 HJEMME: inventory + brugt -> spørger om køb igen
# =========================================================
with tab_home:
    st.subheader("🏠 Varer derhjemme")
    st.caption("Når du markerer en vare som købt, ryger den automatisk herind med en placering.")

    # If user pressed "Brugt" earlier, show prompt at top
    used_prompt = S.get("used_prompt")
    if used_prompt:
        st.markdown('<div class="k-card">', unsafe_allow_html=True)
        st.markdown(f'<div class="k-title">Brugt: {used_prompt.get("name","")}</div>', unsafe_allow_html=True)
        st.markdown('<div class="k-muted">Skal den tilføjes til indkøbslisten igen?</div>', unsafe_allow_html=True)

        add_again = st.button("✅ Ja, tilføj til indkøbslisten")
        no_thanks = st.button("❌ Nej")
        if add_again:
            # Use memory defaults if available
            nm = used_prompt.get("name", "")
            mk = mem_key(nm)
            mem = S["memory"].get(mk, {})
            add_to_shopping(
                name=nm,
                qty=int(mem.get("default_qty", 1) or 1),
                category=mem.get("category", "Andet"),
                store=mem.get("store", "Netto"),
            )
            S["used_prompt"] = None
            persist()
            st.success("Tilføjet ✅")
            st.rerun()
        if no_thanks:
            S["used_prompt"] = None
            persist()
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    # Filters
    q = st.text_input("Søg i hjemme-listen", placeholder="Søg…")

    # Group home items by location then category then name
    home = list(S["home_items"])
    if q.strip():
        qq = q.strip().lower()
        home = [x for x in home if qq in (x.get("name", "").lower())]

    home.sort(key=lambda x: (x.get("location", ""), x.get("category", ""), x.get("name", "").lower()))

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
            st.markdown(
                f'<div class="k-muted">{it.get("category","")} · Senest tilføjet: {human_time(it.get("added_at"))}</div>',
                unsafe_allow_html=True,
            )

            # Actions
            if st.button("🍽️ Brugt", key=f"used_{it['id']}"):
                # Decrement qty; if reaches 0, remove
                it["qty"] = max(0, int(it.get("qty", 1)) - 1)
                it["last_used_at"] = now_iso()
                if it["qty"] <= 0:
                    delete_home_item(it["id"])
                else:
                    persist()
                # prompt to add to shopping
                S["used_prompt"] = {"home_item_id": it["id"], "name": it.get("name", "")}
                persist()
                st.rerun()

            with st.expander("Rediger", expanded=False):
                new_qty = st.number_input("Antal", min_value=0, value=int(it.get("qty", 1)), step=1, key=f"hqty_{it['id']}")
                new_loc = st.selectbox("Placering", S["home_locations"], index=S["home_locations"].index(loc) if loc in S["home_locations"] else 0, key=f"hloc_{it['id']}")
                if st.button("💾 Gem", key=f"hsave_{it['id']}"):
                    it["qty"] = int(new_qty)
                    it["location"] = new_loc
                    if it["qty"] <= 0:
                        delete_home_item(it["id"])
                    else:
                        persist()
                    st.rerun()

                if st.button("🗑️ Slet", key=f"hdel_{it['id']}"):
                    delete_home_item(it["id"])
                    st.rerun()

            st.markdown("</div>", unsafe_allow_html=True)


# =========================================================
# ⭐ STANDARDVARER: grouped by category, tap to add
# =========================================================
with tab_standard:
    st.subheader("⭐ Standardvarer")
    st.caption("Tryk for at tilføje direkte til indkøbslisten. Sorteret efter kategori.")

    std = list(S["standard_items"])
    std.sort(key=lambda x: (x.get("category", ""), x.get("name", "").lower(), x.get("store", "")))

    if not std:
        st.info("Ingen standardvarer endnu. Markér en vare som standard, når du tilføjer den.")
    else:
        last_cat = None
        for it in std:
            cat = it.get("category", "Andet")
            if cat != last_cat:
                st.markdown(f"#### {cat}")
                last_cat = cat

            st.markdown('<div class="k-card">', unsafe_allow_html=True)
            st.markdown(f'<div class="k-title">{it.get("name","")}</div>', unsafe_allow_html=True)
            st.markdown(f'<div class="k-muted">{it.get("store","")} · Standard antal: {it.get("default_qty",1)}</div>', unsafe_allow_html=True)

            if st.button("➕ Tilføj til indkøbslisten", key=f"stdadd_{it['id']}"):
                add_to_shopping(it["name"], int(it.get("default_qty", 1)), it.get("category", "Andet"), it.get("store", "Netto"))
                # update memory too
                upsert_memory(it["name"], it.get("category", "Andet"), it.get("store", "Netto"), int(it.get("default_qty", 1)), True)
                st.rerun()

            with st.expander("Rediger / slet", expanded=False):
                new_qty = st.number_input("Standard antal", min_value=1, value=int(it.get("default_qty", 1)), step=1, key=f"stdq_{it['id']}")
                new_store = st.selectbox("Butik", S["stores"], index=S["stores"].index(it.get("store")) if it.get("store") in S["stores"] else 0, key=f"stds_{it['id']}")
                if st.button("💾 Gem", key=f"stdsave_{it['id']}"):
                    it["default_qty"] = int(new_qty)
                    it["store"] = new_store
                    persist()
                    st.rerun()

                if st.button("🗑️ Slet standardvare", key=f"stddel_{it['id']}"):
                    delete_standard_item(it["id"])
                    st.rerun()

            st.markdown("</div>", unsafe_allow_html=True)


# =========================================================
# ⚙️ SETTINGS: manage stores/categories/locations
# =========================================================
with tab_settings:
    st.subheader("⚙️ Indstillinger")
    st.caption("Her kan du tilpasse butikker, kategorier og placeringer.")

    with st.expander("Butikker", expanded=False):
        new_store = st.text_input("Tilføj butik", placeholder="Fx Meny")
        if st.button("➕ Tilføj butik"):
            ns = (new_store or "").strip()
            if ns and ns not in S["stores"]:
                S["stores"].append(ns)
                persist()
                st.rerun()
        st.write(" • " + " • ".join(S["stores"]))

    with st.expander("Kategorier", expanded=False):
        new_cat = st.text_input("Tilføj kategori", placeholder="Fx Snacks")
        if st.button("➕ Tilføj kategori"):
            nc = (new_cat or "").strip()
            if nc and nc not in S["categories"]:
                S["categories"].append(nc)
                persist()
                st.rerun()
        st.write(" • " + " • ".join(S["categories"]))

    with st.expander("Placeringer (Hjemme)", expanded=False):
        new_loc = st.text_input("Tilføj placering", placeholder="Fx Skur")
        if st.button("➕ Tilføj placering"):
            nl = (new_loc or "").strip()
            if nl and nl not in S["home_locations"]:
                S["home_locations"].append(nl)
                persist()
                st.rerun()
        st.write(" • " + " • ".join(S["home_locations"]))

    st.divider()
    st.write("### Import/Export")
    export_blob = json.dumps(
        {
            "shopping_items": S["shopping_items"],
            "standard_items": S["standard_items"],
            "home_items": S["home_items"],
            "memory": S["memory"],
            "stores": S["stores"],
            "categories": S["categories"],
            "home_locations": S["home_locations"],
            "settings": S["settings"],
            "meta": S["meta"],
        },
        ensure_ascii=False,
        indent=2,
    )
    st.download_button("⬇️ Eksportér data (JSON)", data=export_blob, file_name="shopping_v2_export.json", mime="application/json")

    uploaded = st.file_uploader("Importér data (shopping_v2_export.json)", type=["json"])
    if uploaded is not None:
        try:
            payload = json.loads(uploaded.read().decode("utf-8"))
            for key in ["shopping_items", "standard_items", "home_items", "memory", "stores", "categories", "home_locations", "settings", "meta"]:
                if key in payload:
                    S[key] = payload[key]
            # ensure ids
            S["shopping_items"] = ensure_item_ids(S["shopping_items"])
            S["standard_items"] = ensure_item_ids(S["standard_items"])
            S["home_items"] = ensure_item_ids(S["home_items"])
            persist()
            st.success("Importeret ✅")
            st.rerun()
        except Exception as e:
            st.error(f"Kunne ikke importere: {e}")
