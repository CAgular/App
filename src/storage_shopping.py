# src/storage_shopping.py
# -*- coding: utf-8 -*-
import sqlite3
import uuid
from typing import List, Tuple, Optional

from src.config import DB_PATH


def _conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def _table_cols(con: sqlite3.Connection, table: str) -> set[str]:
    rows = con.execute(f"PRAGMA table_info({table})").fetchall()
    # row[1] is column name
    return {r[1] for r in rows}


def init_shopping_tables() -> None:
    """
    Create tables + simple migrations.

    We store categories on both lists:
      - shopping_items.category
      - pantry_items.category

    Migration note:
      If an older pantry_items had 'location' column, we add 'category' and copy location->category.
    """
    with _conn() as con:
        cur = con.cursor()

        cur.execute("""
        CREATE TABLE IF NOT EXISTS shopping_items (
            uid TEXT PRIMARY KEY,
            text TEXT NOT NULL,
            qty REAL NOT NULL DEFAULT 1,
            category TEXT NOT NULL DEFAULT 'Ukategoriseret',
            created_at TEXT DEFAULT (datetime('now'))
        )
        """)

        # Create pantry table in its new shape (category instead of location)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS pantry_items (
            uid TEXT PRIMARY KEY,
            text TEXT NOT NULL,
            qty REAL NOT NULL DEFAULT 1,
            category TEXT NOT NULL DEFAULT 'Ukategoriseret',
            created_at TEXT DEFAULT (datetime('now'))
        )
        """)

        # Migrations
        cols_shopping = _table_cols(con, "shopping_items")
        if "category" not in cols_shopping:
            cur.execute("ALTER TABLE shopping_items ADD COLUMN category TEXT NOT NULL DEFAULT 'Ukategoriseret'")

        cols_pantry = _table_cols(con, "pantry_items")

        # If older schema had location, copy it into category (best-effort)
        if "location" in cols_pantry and "category" not in cols_pantry:
            cur.execute("ALTER TABLE pantry_items ADD COLUMN category TEXT NOT NULL DEFAULT 'Ukategoriseret'")
            cur.execute("UPDATE pantry_items SET category = COALESCE(location, 'Ukategoriseret')")

        if "category" not in cols_pantry:
            # table existed but without category (unlikely), ensure it exists
            cur.execute("ALTER TABLE pantry_items ADD COLUMN category TEXT NOT NULL DEFAULT 'Ukategoriseret'")

        con.commit()


# -----------------------------
# Fetch
# -----------------------------
def fetch_shopping() -> List[Tuple[str, str, float, str]]:
    with _conn() as con:
        rows = con.execute("""
            SELECT uid, text, qty, category
            FROM shopping_items
            ORDER BY category COLLATE NOCASE, created_at ASC
        """).fetchall()
    return [(r[0], r[1], float(r[2]), r[3] or "Ukategoriseret") for r in rows]


def fetch_pantry() -> List[Tuple[str, str, float, str]]:
    with _conn() as con:
        # if an old DB still has location, coalesce into category
        cols = _table_cols(con, "pantry_items")
        if "location" in cols and "category" in cols:
            q = """
                SELECT uid, text, qty, COALESCE(category, location, 'Ukategoriseret') as cat
                FROM pantry_items
                ORDER BY cat COLLATE NOCASE, created_at ASC
            """
        elif "location" in cols:
            q = """
                SELECT uid, text, qty, COALESCE(location, 'Ukategoriseret') as cat
                FROM pantry_items
                ORDER BY cat COLLATE NOCASE, created_at ASC
            """
        else:
            q = """
                SELECT uid, text, qty, COALESCE(category, 'Ukategoriseret') as cat
                FROM pantry_items
                ORDER BY cat COLLATE NOCASE, created_at ASC
            """
        rows = con.execute(q).fetchall()
    return [(r[0], r[1], float(r[2]), r[3] or "Ukategoriseret") for r in rows]


# -----------------------------
# Shopping operations
# -----------------------------
def add_shopping(text: str, qty: float, category: str) -> None:
    text = (text or "").strip()
    if not text:
        return

    qty = float(qty) if qty and qty > 0 else 1.0
    category = (category or "Ukategoriseret").strip() or "Ukategoriseret"

    with _conn() as con:
        con.execute(
            "INSERT INTO shopping_items (uid, text, qty, category) VALUES (?, ?, ?, ?)",
            (str(uuid.uuid4()), text, qty, category),
        )
        con.commit()


def delete_shopping(uid: str) -> None:
    with _conn() as con:
        con.execute("DELETE FROM shopping_items WHERE uid = ?", (uid,))
        con.commit()


def pop_shopping(uid: str) -> Optional[Tuple[str, float, str]]:
    """
    Remove a shopping row and return (text, qty, category).
    """
    with _conn() as con:
        cur = con.cursor()
        row = cur.execute(
            "SELECT text, qty, category FROM shopping_items WHERE uid=?",
            (uid,),
        ).fetchone()

        if not row:
            return None

        cur.execute("DELETE FROM shopping_items WHERE uid=?", (uid,))
        con.commit()

        text, qty, category = row
        return (text, float(qty), (category or "Ukategoriseret"))


# -----------------------------
# Pantry operations (category-based)
# -----------------------------
def pantry_add_or_merge(text: str, qty: float, category: str) -> None:
    """
    Add to pantry and merge qty if same text+category exists.
    """
    text = (text or "").strip()
    if not text:
        return
    qty = float(qty) if qty and qty > 0 else 1.0
    category = (category or "Ukategoriseret").strip() or "Ukategoriseret"
    text_key = text.lower()

    with _conn() as con:
        cur = con.cursor()

        # merge on lower(text) + category
        row = cur.execute(
            "SELECT uid, qty FROM pantry_items WHERE lower(text)=? AND COALESCE(category,'Ukategoriseret')=?",
            (text_key, category),
        ).fetchone()

        if row:
            puid, old_qty = row
            cur.execute(
                "UPDATE pantry_items SET qty=? WHERE uid=?",
                (float(old_qty) + qty, puid),
            )
        else:
            cur.execute(
                "INSERT INTO pantry_items (uid, text, qty, category) VALUES (?, ?, ?, ?)",
                (str(uuid.uuid4()), text, qty, category),
            )

        con.commit()


def pantry_used_add_back(uid: str, qty_used: float) -> Optional[Tuple[str, str]]:
    """
    Use item from pantry:
      - subtract qty_used
      - delete row if qty <= 0
      - return (text, category) so UI can add back to shopping with same category
    """
    qty_used = float(qty_used) if qty_used and qty_used > 0 else 1.0

    with _conn() as con:
        cur = con.cursor()
        row = cur.execute(
            "SELECT text, qty, COALESCE(category,'Ukategoriseret') FROM pantry_items WHERE uid=?",
            (uid,),
        ).fetchone()

        if not row:
            return None

        text, qty, category = row
        remaining = float(qty) - qty_used

        if remaining > 0:
            cur.execute("UPDATE pantry_items SET qty=? WHERE uid=?", (remaining, uid))
        else:
            cur.execute("DELETE FROM pantry_items WHERE uid=?", (uid,))

        con.commit()
        return (text, category or "Ukategoriseret")
