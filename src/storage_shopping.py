# src/storage_shopping.py
# -*- coding: utf-8 -*-
import sqlite3
import uuid
from typing import List, Tuple, Optional

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
    """
    con = _conn()
    cur = con.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS shopping_items (
        uid TEXT PRIMARY KEY,
        text TEXT NOT NULL,
        qty REAL NOT NULL DEFAULT 1,
        category TEXT NOT NULL DEFAULT 'Ukategoriseret',
        is_standard INTEGER NOT NULL DEFAULT 0,
        created_at TEXT DEFAULT (datetime('now'))
    )
    """)

    # create minimal pantry (safe for migrations)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS pantry_items (
        uid TEXT PRIMARY KEY,
        text TEXT NOT NULL,
        qty REAL NOT NULL DEFAULT 1,
        created_at TEXT DEFAULT (datetime('now'))
    )
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS standard_items (
        text_key TEXT PRIMARY KEY,
        text TEXT NOT NULL,
        category TEXT NOT NULL DEFAULT 'Ukategoriseret',
        default_qty REAL NOT NULL DEFAULT 1,
        created_at TEXT DEFAULT (datetime('now'))
    )
    """)

    # migrations shopping
    cols_s = _table_cols(con, "shopping_items")
    if "category" not in cols_s:
        cur.execute("ALTER TABLE shopping_items ADD COLUMN category TEXT NOT NULL DEFAULT 'Ukategoriseret'")
    if "is_standard" not in cols_s:
        cur.execute("ALTER TABLE shopping_items ADD COLUMN is_standard INTEGER NOT NULL DEFAULT 0")

    # migrations pantry
    cols_p = _table_cols(con, "pantry_items")
    if "category" not in cols_p:
        cur.execute("ALTER TABLE pantry_items ADD COLUMN category TEXT NOT NULL DEFAULT 'Ukategoriseret'")
        cols_p = _table_cols(con, "pantry_items")

    if "location" in cols_p:
        cur.execute("UPDATE pantry_items SET category = COALESCE(category, location, 'Ukategoriseret')")

    if "is_standard" not in cols_p:
        cur.execute("ALTER TABLE pantry_items ADD COLUMN is_standard INTEGER NOT NULL DEFAULT 0")

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
    """
    Remove a standard from catalog and also clear is_standard flags on matching rows.
    """
    k = _key(text)
    if not k:
        return
    con = _conn()
    cur = con.cursor()
    cur.execute("DELETE FROM standard_items WHERE text_key=?", (k,))
    cur.execute("UPDATE shopping_items SET is_standard=0 WHERE lower(text)=?", (k,))
    cur.execute("UPDATE pantry_items SET is_standard=0 WHERE lower(text)=?", (k,))
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
    rows = con.execute("""
        SELECT uid, text, qty, COALESCE(category,'Ukategoriseret'), COALESCE(is_standard,0)
        FROM shopping_items
        ORDER BY COALESCE(category,'Ukategoriseret') COLLATE NOCASE, created_at ASC
    """).fetchall()
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
    """
    Toggle standard flag for a shopping row.
    Returns (text, category, qty) for updating standard catalog.
    """
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
    category = (category or "Ukategoriseret").strip() or "Ukategoret"
    if category == "Ukategoret":
        category = "Ukategoriseret"
    is_standard = 1 if is_standard else 0
    text_key = text.lower()

    con = _conn()
    cur = con.cursor()

    row = cur.execute(
        """
        SELECT uid, qty, COALESCE(is_standard,0)
        FROM pantry_items
        WHERE lower(text)=? AND COALESCE(category,'Ukategoriseret')=?
        """,
        (text_key, category),
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
