# src/storage_shopping.py
# -*- coding: utf-8 -*-
import sqlite3
import uuid
from typing import List, Tuple, Optional, Dict

from src.config import DB_PATH

# Reuse one connection (faster than opening/closing per function)
_CONN: Optional[sqlite3.Connection] = None


def _conn() -> sqlite3.Connection:
    global _CONN
    if _CONN is None:
        _CONN = sqlite3.connect(DB_PATH, check_same_thread=False)
    return _CONN


def _table_cols(con: sqlite3.Connection, table: str) -> set[str]:
    rows = con.execute(f"PRAGMA table_info({table})").fetchall()
    return {r[1] for r in rows}


def _key(text: str) -> str:
    return (text or "").strip().lower()


def init_shopping_tables() -> None:
    """
    shopping_items: uid, text, qty, category, is_standard, created_at
    pantry_items:   uid, text, qty, category, is_standard, created_at
    standard_items: text_key, text, category, default_qty, created_at

    recipes:        uid, name, is_done, created_at
    recipe_items:   uid, recipe_uid, text, qty, category, is_standard, created_at

    meal_plan:      uid, day_date, recipe_uid, title, servings, note, created_at
    """
    con = _conn()
    cur = con.cursor()

    # -----------------------------
    # Core tables
    # -----------------------------
    cur.execute(
        """
    CREATE TABLE IF NOT EXISTS shopping_items (
        uid TEXT PRIMARY KEY,
        text TEXT NOT NULL,
        qty REAL NOT NULL DEFAULT 1,
        category TEXT NOT NULL DEFAULT 'Ukategoriseret',
        is_standard INTEGER NOT NULL DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now'))
    )
    """
    )

    # Create minimal pantry (safe for migrations)
    cur.execute(
        """
    CREATE TABLE IF NOT EXISTS pantry_items (
        uid TEXT PRIMARY KEY,
        text TEXT NOT NULL,
        qty REAL NOT NULL DEFAULT 1,
        created_at TEXT DEFAULT (datetime('now'))
    )
    """
    )

    cur.execute(
        """
    CREATE TABLE IF NOT EXISTS standard_items (
        text_key TEXT PRIMARY KEY,
        text TEXT NOT NULL,
        category TEXT NOT NULL DEFAULT 'Ukategoriseret',
        default_qty REAL NOT NULL DEFAULT 1,
        created_at TEXT DEFAULT (datetime('now'))
    )
    """
    )

    # -----------------------------
    # Recipes
    # -----------------------------
    cur.execute(
        """
    CREATE TABLE IF NOT EXISTS recipes (
        uid TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        is_done INTEGER NOT NULL DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now'))
    )
    """
    )

    cur.execute(
        """
    CREATE TABLE IF NOT EXISTS recipe_items (
        uid TEXT PRIMARY KEY,
        recipe_uid TEXT NOT NULL,
        text TEXT NOT NULL,
        qty REAL NOT NULL DEFAULT 1,
        category TEXT NOT NULL DEFAULT 'Ukategoriseret',
        is_standard INTEGER NOT NULL DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now'))
    )
    """
    )

    # -----------------------------
    # Meal plan (used by ugemenu)
    # -----------------------------
    cur.execute(
        """
    CREATE TABLE IF NOT EXISTS meal_plan (
        uid TEXT PRIMARY KEY,
        day_date TEXT NOT NULL,
        recipe_uid TEXT,
        title TEXT,
        servings REAL NOT NULL DEFAULT 1,
        note TEXT,
        created_at TEXT DEFAULT (datetime('now'))
    )
    """
    )

    # -----------------------------
    # Migrations: shopping_items
    # -----------------------------
    cols_s = _table_cols(con, "shopping_items")
    if "category" not in cols_s:
        cur.execute("ALTER TABLE shopping_items ADD COLUMN category TEXT NOT NULL DEFAULT 'Ukategoriseret'")
    if "is_standard" not in cols_s:
        cur.execute("ALTER TABLE shopping_items ADD COLUMN is_standard INTEGER NOT NULL DEFAULT 0")

    # -----------------------------
    # Migrations: pantry_items
    # -----------------------------
    cols_p = _table_cols(con, "pantry_items")
    if "category" not in cols_p:
        cur.execute("ALTER TABLE pantry_items ADD COLUMN category TEXT NOT NULL DEFAULT 'Ukategoriseret'")
        cols_p = _table_cols(con, "pantry_items")

    if "location" in cols_p:
        cur.execute("UPDATE pantry_items SET category = COALESCE(category, location, 'Ukategoriseret')")

    if "is_standard" not in cols_p:
        cur.execute("ALTER TABLE pantry_items ADD COLUMN is_standard INTEGER NOT NULL DEFAULT 0")

    # -----------------------------
    # Migrations: recipes
    # -----------------------------
    cols_r = _table_cols(con, "recipes")
    if "is_done" not in cols_r:
        cur.execute("ALTER TABLE recipes ADD COLUMN is_done INTEGER NOT NULL DEFAULT 0")

    # -----------------------------
    # Migrations: meal_plan
    # -----------------------------
    cols_mp = _table_cols(con, "meal_plan")
    if "servings" not in cols_mp:
        cur.execute("ALTER TABLE meal_plan ADD COLUMN servings REAL NOT NULL DEFAULT 1")
    if "note" not in cols_mp:
        cur.execute("ALTER TABLE meal_plan ADD COLUMN note TEXT")
    if "title" not in cols_mp:
        cur.execute("ALTER TABLE meal_plan ADD COLUMN title TEXT")

    con.commit()


# -----------------------------
# Standards
# -----------------------------
def upsert_standard(text: str, category: str, default_qty: float = 1.0) -> None:
    text = (text or "").strip()
    if not text:
        return
    category = (category or "Ukategoriseret").strip() or "Ukategoriseret"
    default_qty = float(default_qty) if default_qty and default_qty > 0 else 1.0

    con = _conn()
    con.execute(
        """
        INSERT INTO standard_items (text_key, text, category, default_qty)
        VALUES (?, ?, ?, ?)
        ON CONFLICT(text_key) DO UPDATE SET
          text=excluded.text,
          category=excluded.category,
          default_qty=excluded.default_qty
        """,
        (_key(text), text, category, default_qty),
    )
    con.commit()


def delete_standard(text: str) -> None:
    k = _key(text)
    if not k:
        return
    con = _conn()
    cur = con.cursor()
    cur.execute("DELETE FROM standard_items WHERE text_key=?", (k,))
    cur.execute("UPDATE shopping_items SET is_standard=0 WHERE lower(text)=?", (k,))
    cur.execute("UPDATE pantry_items SET is_standard=0 WHERE lower(text)=?", (k,))
    cur.execute("UPDATE recipe_items SET is_standard=0 WHERE lower(text)=?", (k,))
    con.commit()


def fetch_standards() -> List[Tuple[str, str, float]]:
    con = _conn()
    rows = con.execute(
        """
        SELECT text, COALESCE(category,'Ukategoriseret'), COALESCE(default_qty,1)
        FROM standard_items
        ORDER BY COALESCE(category,'Ukategoriseret') COLLATE NOCASE, text COLLATE NOCASE
        """
    ).fetchall()
    return [(r[0], r[1] or "Ukategoriseret", float(r[2])) for r in rows]


# -----------------------------
# Fetch lists
# -----------------------------
def fetch_shopping() -> List[Tuple[str, str, float, str, int]]:
    con = _conn()
    rows = con.execute(
        """
        SELECT uid, text, qty, COALESCE(category,'Ukategoriseret'), COALESCE(is_standard,0)
        FROM shopping_items
        ORDER BY COALESCE(category,'Ukategoriseret') COLLATE NOCASE, created_at ASC
        """
    ).fetchall()
    return [(r[0], r[1], float(r[2]), r[3] or "Ukategoriseret", int(r[4] or 0)) for r in rows]


def fetch_pantry() -> List[Tuple[str, str, float, str, int]]:
    con = _conn()
    cols = _table_cols(con, "pantry_items")
    if "location" in cols:
        q = """
            SELECT uid, text, qty,
                   COALESCE(category, location, 'Ukategoriseret') as cat,
                   COALESCE(is_standard,0)
            FROM pantry_items
            ORDER BY cat COLLATE NOCASE, created_at ASC
        """
    else:
        q = """
            SELECT uid, text, qty,
                   COALESCE(category, 'Ukategoriseret') as cat,
                   COALESCE(is_standard,0)
            FROM pantry_items
            ORDER BY cat COLLATE NOCASE, created_at ASC
        """
    rows = con.execute(q).fetchall()
    return [(r[0], r[1], float(r[2]), r[3] or "Ukategoriseret", int(r[4] or 0)) for r in rows]


def get_pantry_item(uid: str) -> Optional[Tuple[str, float, str, int]]:
    con = _conn()
    cols = _table_cols(con, "pantry_items")
    if "location" in cols:
        q = "SELECT text, qty, COALESCE(category, location, 'Ukategoriseret'), COALESCE(is_standard,0) FROM pantry_items WHERE uid=?"
    else:
        q = "SELECT text, qty, COALESCE(category,'Ukategoriseret'), COALESCE(is_standard,0) FROM pantry_items WHERE uid=?"
    row = con.execute(q, (uid,)).fetchone()
    if not row:
        return None
    return (row[0], float(row[1]), row[2] or "Ukategoriseret", int(row[3] or 0))


# -----------------------------
# Shopping operations
# -----------------------------
def add_shopping(text: str, qty: float, category: str, is_standard: int = 0) -> None:
    text = (text or "").strip()
    if not text:
        return
    qty = float(qty) if qty and qty > 0 else 1.0
    category = (category or "Ukategoriseret").strip() or "Ukategoriseret"
    is_standard = 1 if is_standard else 0

    con = _conn()
    con.execute(
        "INSERT INTO shopping_items (uid, text, qty, category, is_standard) VALUES (?, ?, ?, ?, ?)",
        (str(uuid.uuid4()), text, qty, category, is_standard),
    )
    con.commit()


def delete_shopping(uid: str) -> None:
    con = _conn()
    con.execute("DELETE FROM shopping_items WHERE uid = ?", (uid,))
    con.commit()


def pop_shopping(uid: str) -> Optional[Tuple[str, float, str, int]]:
    con = _conn()
    cur = con.cursor()
    row = cur.execute(
        "SELECT text, qty, COALESCE(category,'Ukategoriseret'), COALESCE(is_standard,0) FROM shopping_items WHERE uid=?",
        (uid,),
    ).fetchone()
    if not row:
        return None
    cur.execute("DELETE FROM shopping_items WHERE uid=?", (uid,))
    con.commit()
    text, qty, category, is_std = row
    return (text, float(qty), category or "Ukategoriseret", int(is_std or 0))


def set_shopping_standard(uid: str, is_standard: int) -> Optional[Tuple[str, str, float]]:
    con = _conn()
    cur = con.cursor()
    row = cur.execute(
        "SELECT text, COALESCE(category,'Ukategoriseret'), qty FROM shopping_items WHERE uid=?",
        (uid,),
    ).fetchone()
    if not row:
        return None
    text, category, qty = row
    cur.execute("UPDATE shopping_items SET is_standard=? WHERE uid=?", (1 if is_standard else 0, uid))
    con.commit()
    return (text, category, float(qty))


# -----------------------------
# Pantry operations
# -----------------------------
def pantry_add_or_merge(text: str, qty: float, category: str, is_standard: int = 0) -> None:
    text = (text or "").strip()
    if not text:
        return
    qty = float(qty) if qty and qty > 0 else 1.0
    category = (category or "Ukategoriseret").strip() or "Ukategoriseret"
    if category.lower() == "ukategoret":
        category = "Ukategoriseret"
    is_standard = 1 if is_standard else 0

    con = _conn()
    cur = con.cursor()
    row = cur.execute(
        """
        SELECT uid, qty, COALESCE(is_standard,0)
        FROM pantry_items
        WHERE lower(text)=? AND COALESCE(category,'Ukategoriseret')=?
        """,
        (text.lower(), category),
    ).fetchone()

    if row:
        puid, old_qty, old_std = row
        new_std = 1 if (int(old_std or 0) == 1 or is_standard == 1) else 0
        cur.execute("UPDATE pantry_items SET qty=?, is_standard=? WHERE uid=?", (float(old_qty) + qty, new_std, puid))
    else:
        cur.execute(
            "INSERT INTO pantry_items (uid, text, qty, category, is_standard) VALUES (?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), text, qty, category, is_standard),
        )

    con.commit()


def pantry_consume(uid: str, qty_used: float) -> Optional[Tuple[str, str, int]]:
    qty_used = float(qty_used) if qty_used and qty_used > 0 else 1.0

    con = _conn()
    cur = con.cursor()
    row = cur.execute(
        "SELECT text, qty, COALESCE(category,'Ukategoriseret'), COALESCE(is_standard,0) FROM pantry_items WHERE uid=?",
        (uid,),
    ).fetchone()
    if not row:
        return None
    text, qty, category, is_std = row
    remaining = float(qty) - qty_used
    if remaining > 0:
        cur.execute("UPDATE pantry_items SET qty=? WHERE uid=?", (remaining, uid))
    else:
        cur.execute("DELETE FROM pantry_items WHERE uid=?", (uid,))
    con.commit()
    return (text, category or "Ukategoriseret", int(is_std or 0))


def set_pantry_standard(uid: str, is_standard: int) -> Optional[Tuple[str, str, float]]:
    con = _conn()
    cur = con.cursor()
    row = cur.execute(
        "SELECT text, COALESCE(category,'Ukategoriseret'), qty FROM pantry_items WHERE uid=?",
        (uid,),
    ).fetchone()
    if not row:
        return None
    text, category, qty = row
    cur.execute("UPDATE pantry_items SET is_standard=? WHERE uid=?", (1 if is_standard else 0, uid))
    con.commit()
    return (text, category, float(qty))


def pantry_move_category(uid: str, new_category: str) -> bool:
    new_category = (new_category or "Ukategoriseret").strip() or "Ukategoriseret"

    con = _conn()
    cur = con.cursor()
    row = cur.execute(
        "SELECT text, qty, COALESCE(category,'Ukategoriseret'), COALESCE(is_standard,0) FROM pantry_items WHERE uid=?",
        (uid,),
    ).fetchone()
    if not row:
        return False

    text, qty, old_cat, is_std = row
    if (old_cat or "Ukategoriseret") == new_category:
        return False

    row2 = cur.execute(
        """
        SELECT uid, qty, COALESCE(is_standard,0)
        FROM pantry_items
        WHERE lower(text)=? AND COALESCE(category,'Ukategoriseret')=?
        """,
        (text.strip().lower(), new_category),
    ).fetchone()

    if row2:
        uid2, qty2, is_std2 = row2
        new_qty = float(qty2) + float(qty)
        new_std = 1 if (int(is_std or 0) == 1 or int(is_std2 or 0) == 1) else 0
        cur.execute("UPDATE pantry_items SET qty=?, is_standard=? WHERE uid=?", (new_qty, new_std, uid2))
        cur.execute("DELETE FROM pantry_items WHERE uid=?", (uid,))
    else:
        cur.execute("UPDATE pantry_items SET category=? WHERE uid=?", (new_category, uid))

    con.commit()
    return True


# -----------------------------
# Recipes (drafts + finished)
# -----------------------------
def add_recipe(name: str, is_done: int = 0) -> Optional[str]:
    name = (name or "").strip()
    if not name:
        return None
    con = _conn()
    uid = str(uuid.uuid4())
    con.execute("INSERT INTO recipes (uid, name, is_done) VALUES (?, ?, ?)", (uid, name, 1 if is_done else 0))
    con.commit()
    return uid


def delete_recipe(recipe_uid: str) -> None:
    con = _conn()
    cur = con.cursor()
    cur.execute("DELETE FROM recipe_items WHERE recipe_uid=?", (recipe_uid,))
    cur.execute("DELETE FROM recipes WHERE uid=?", (recipe_uid,))
    cur.execute("UPDATE meal_plan SET recipe_uid=NULL WHERE recipe_uid=?", (recipe_uid,))
    con.commit()


def set_recipe_done(recipe_uid: str, is_done: int) -> None:
    con = _conn()
    con.execute("UPDATE recipes SET is_done=? WHERE uid=?", (1 if is_done else 0, recipe_uid))
    con.commit()


def fetch_recipes(done: Optional[int] = None) -> List[Tuple[str, str, int]]:
    """
    done=None => all
    done=0 => drafts
    done=1 => finished
    Returns: (uid, name, is_done)
    """
    con = _conn()
    if done is None:
        rows = con.execute(
            "SELECT uid, name, COALESCE(is_done,0) FROM recipes ORDER BY COALESCE(is_done,0) ASC, name COLLATE NOCASE"
        ).fetchall()
    else:
        rows = con.execute(
            "SELECT uid, name, COALESCE(is_done,0) FROM recipes WHERE COALESCE(is_done,0)=? ORDER BY name COLLATE NOCASE",
            (1 if done else 0,),
        ).fetchall()
    return [(r[0], r[1], int(r[2] or 0)) for r in rows]


def fetch_recipe_items(recipe_uid: str) -> List[Tuple[str, str, float, str, int]]:
    con = _conn()
    rows = con.execute(
        """
        SELECT uid, text, qty, COALESCE(category,'Ukategoriseret'), COALESCE(is_standard,0)
        FROM recipe_items
        WHERE recipe_uid=?
        ORDER BY COALESCE(category,'Ukategoriseret') COLLATE NOCASE, text COLLATE NOCASE
        """,
        (recipe_uid,),
    ).fetchall()
    return [(r[0], r[1], float(r[2]), r[3] or "Ukategoriseret", int(r[4] or 0)) for r in rows]


def delete_recipe_item(item_uid: str) -> None:
    con = _conn()
    con.execute("DELETE FROM recipe_items WHERE uid=?", (item_uid,))
    con.commit()


def update_recipe_item_qty(item_uid: str, qty: float) -> None:
    qty = float(qty) if qty and qty > 0 else 1.0
    con = _conn()
    con.execute("UPDATE recipe_items SET qty=? WHERE uid=?", (qty, item_uid))
    con.commit()


def recipe_add_or_merge(recipe_uid: str, text: str, qty: float, category: str, is_standard: int = 0) -> None:
    text = (text or "").strip()
    if not text or not recipe_uid:
        return
    qty = float(qty) if qty and qty > 0 else 1.0
    category = (category or "Ukategoriseret").strip() or "Ukategoriseret"
    is_standard = 1 if is_standard else 0

    con = _conn()
    cur = con.cursor()
    row = cur.execute(
        """
        SELECT uid, qty, COALESCE(is_standard,0)
        FROM recipe_items
        WHERE recipe_uid=? AND lower(text)=? AND COALESCE(category,'Ukategoriseret')=?
        """,
        (recipe_uid, text.strip().lower(), category),
    ).fetchone()

    if row:
        uid, old_qty, old_std = row
        new_qty = float(old_qty) + qty
        new_std = 1 if (int(old_std or 0) == 1 or is_standard == 1) else 0
        cur.execute("UPDATE recipe_items SET qty=?, is_standard=? WHERE uid=?", (new_qty, new_std, uid))
    else:
        cur.execute(
            """
            INSERT INTO recipe_items (uid, recipe_uid, text, qty, category, is_standard)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (str(uuid.uuid4()), recipe_uid, text, qty, category, is_standard),
        )

    con.commit()


def add_shopping_from_recipe(
    recipe_uid: str,
    multiplier: float = 1.0,
    check_pantry_first: bool = True,
) -> Dict[str, int]:
    """
    Add ingredients from ONE recipe to shopping list.
    If check_pantry_first=True, skip ingredients whose text exists in pantry (name-match).
    Uses ingredient category exactly as stored on recipe item.

    Returns: {"added": int, "skipped_home": int}
    """
    multiplier = float(multiplier) if multiplier and float(multiplier) > 0 else 1.0

    pantry_keys = set()
    if check_pantry_first:
        pantry_rows = fetch_pantry()
        pantry_keys = {_key(t) for (_uid, t, _q, _c, _s) in pantry_rows if _key(t)}

    items = fetch_recipe_items(recipe_uid)  # (uid,text,qty,cat,is_std)

    added = 0
    skipped = 0
    for _uid, text, qty, cat, is_std in items:
        tk = _key(text)
        if check_pantry_first and tk in pantry_keys:
            skipped += 1
            continue
        add_shopping(text=text, qty=float(qty) * multiplier, category=cat, is_standard=int(is_std or 0))
        added += 1

    return {"added": added, "skipped_home": skipped}


# -----------------------------
# Meal plan
# -----------------------------
def set_meal_for_date(day_date: str, recipe_uid: Optional[str], title: str, servings: float = 1.0, note: str = "") -> None:
    day_date = (day_date or "").strip()
    if not day_date:
        return
    title = (title or "").strip()
    servings = float(servings) if servings and float(servings) > 0 else 1.0
    note = (note or "").strip()

    con = _conn()
    cur = con.cursor()
    existing = cur.execute("SELECT uid FROM meal_plan WHERE day_date=?", (day_date,)).fetchone()
    if existing:
        uid = existing[0]
        cur.execute(
            "UPDATE meal_plan SET recipe_uid=?, title=?, servings=?, note=? WHERE uid=?",
            (recipe_uid, title, servings, note, uid),
        )
    else:
        cur.execute(
            """
            INSERT INTO meal_plan (uid, day_date, recipe_uid, title, servings, note)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (str(uuid.uuid4()), day_date, recipe_uid, title, servings, note),
        )
    con.commit()


def clear_meal_for_date(day_date: str) -> None:
    con = _conn()
    con.execute("DELETE FROM meal_plan WHERE day_date=?", (day_date,))
    con.commit()


def fetch_meal_plan(date_from: str, date_to: str) -> List[Tuple[str, Optional[str], str, float, str]]:
    con = _conn()
    rows = con.execute(
        """
        SELECT day_date, recipe_uid, COALESCE(title,''), COALESCE(servings,1), COALESCE(note,'')
        FROM meal_plan
        WHERE day_date >= ? AND day_date <= ?
        ORDER BY day_date ASC
        """,
        (date_from, date_to),
    ).fetchall()
    return [(r[0], r[1], r[2] or "", float(r[3] or 1), r[4] or "") for r in rows]


# -----------------------------
# Generate shopping list from meal plan
# -----------------------------
def generate_shopping_from_mealplan(
    date_from: str,
    date_to: str,
    check_pantry_first: bool = True,
) -> Dict[str, int]:
    pantry_keys = set()
    if check_pantry_first:
        pantry_rows = fetch_pantry()
        pantry_keys = {_key(t) for (_, t, _, _, _) in pantry_rows if _key(t)}

    plan_rows = fetch_meal_plan(date_from, date_to)

    recipe_servings: Dict[str, float] = {}
    for _day_date, recipe_uid, _title, servings, _note in plan_rows:
        if recipe_uid:
            recipe_servings[recipe_uid] = recipe_servings.get(recipe_uid, 0.0) + float(servings or 1.0)

    if not recipe_servings:
        return {"added": 0, "skipped_home": 0, "merged_items": 0}

    merged: Dict[Tuple[str, str], Dict[str, object]] = {}
    con = _conn()
    cur = con.cursor()

    for ruid, total_servings in recipe_servings.items():
        items = cur.execute(
            """
            SELECT text, qty, COALESCE(category,'Ukategoriseret'), COALESCE(is_standard,0)
            FROM recipe_items
            WHERE recipe_uid=?
            """,
            (ruid,),
        ).fetchall()

        for text, qty, cat, is_std in items:
            t = (text or "").strip()
            if not t:
                continue
            tk = _key(t)
            cat = (cat or "Ukategoriseret").strip() or "Ukategoriseret"

            if check_pantry_first and tk in pantry_keys:
                continue

            key = (tk, cat)
            q = float(qty or 1.0) * float(total_servings or 1.0)

            if key not in merged:
                merged[key] = {"text": t, "qty": q, "category": cat, "is_standard": int(is_std or 0)}
            else:
                merged[key]["qty"] = float(merged[key]["qty"]) + q
                merged[key]["is_standard"] = 1 if (int(merged[key]["is_standard"]) == 1 or int(is_std or 0) == 1) else 0

    added = 0
    for (_tk, _cat), v in merged.items():
        add_shopping(
            text=str(v["text"]),
            qty=float(v["qty"]),
            category=str(v["category"]),
            is_standard=int(v["is_standard"]),
        )
        added += 1

    skipped_home = 0
    if check_pantry_first:
        all_keys = set()
        for ruid in recipe_servings.keys():
            rows = cur.execute("SELECT text FROM recipe_items WHERE recipe_uid=?", (ruid,)).fetchall()
            for (t,) in rows:
                k = _key(t or "")
                if k:
                    all_keys.add(k)
        skipped_home = sum(1 for k in all_keys if k in pantry_keys)

    return {"added": added, "skipped_home": skipped_home, "merged_items": len(merged)}
