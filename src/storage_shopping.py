# -*- coding: utf-8 -*-
import sqlite3
import uuid
from typing import List, Tuple, Optional

from src.config import DB_PATH


def _conn():
    return sqlite3.connect(DB_PATH, check_same_thread=False)


def init_shopping_tables() -> None:
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

        cur.execute("""
        CREATE TABLE IF NOT EXISTS pantry_items (
            uid TEXT PRIMARY KEY,
            text TEXT NOT NULL,
            qty REAL NOT NULL DEFAULT 1,
            location TEXT NOT NULL DEFAULT 'Ukategoriseret',
            created_at TEXT DEFAULT (datetime('now'))
        )
        """)

        # Husker placering pr varenavn (første gang man vælger)
        cur.execute("""
        CREATE TABLE IF NOT EXISTS pantry_location_memory (
            text_key TEXT PRIMARY KEY,
            location TEXT NOT NULL
        )
        """)

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
    return rows


def fetch_pantry() -> List[Tuple[str, str, float, str]]:
    with _conn() as con:
        rows = con.execute("""
            SELECT uid, text, qty, location
            FROM pantry_items
            ORDER BY location COLLATE NOCASE, created_at ASC
        """).fetchall()
    return rows


# -----------------------------
# Shopping operations
# -----------------------------
def add_shopping(text: str, qty: float, category: str) -> None:
    text = (text or "").strip()
    if not text:
        return

    if qty <= 0:
        qty = 1.0
    category = (category or "Ukategoriseret").strip() or "Ukategoriseret"

    uid = str(uuid.uuid4())

    with _conn() as con:
        con.execute(
            "INSERT INTO shopping_items (uid, text, qty, category) VALUES (?, ?, ?, ?)",
            (uid, text, float(qty), category),
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
        return (text, float(qty), category)


# -----------------------------
# Pantry operations
# -----------------------------
def _get_remembered_location(cur, text: str) -> str:
    text_key = text.strip().lower()
    loc_row = cur.execute(
        "SELECT location FROM pantry_location_memory WHERE text_key=?",
        (text_key,),
    ).fetchone()
    return (loc_row[0] if loc_row else "Ukategoriseret") or "Ukategoriseret"


def pantry_add_or_merge(text: str, qty: float) -> str:
    """
    Add to pantry when bought.
    Uses remembered location for text, merges qty if same text+location exists.
    Returns the location used.
    """
    text = (text or "").strip()
    if not text:
        return "Ukategoriseret"
    if qty <= 0:
        qty = 1.0

    with _conn() as con:
        cur = con.cursor()
        location = _get_remembered_location(cur, text)

        # merge on lower(text) + location
        row = cur.execute(
            "SELECT uid, qty FROM pantry_items WHERE lower(text)=? AND location=?",
            (text.lower(), location),
        ).fetchone()

        if row:
            uid, old_qty = row
            cur.execute(
                "UPDATE pantry_items SET qty=? WHERE uid=?",
                (float(old_qty) + float(qty), uid),
            )
        else:
            puid = str(uuid.uuid4())
            cur.execute(
                "INSERT INTO pantry_items (uid, text, qty, location) VALUES (?, ?, ?, ?)",
                (puid, text, float(qty), location),
            )

        con.commit()
        return location


def pantry_set_location(uid: str, text: str, location: str) -> None:
    """
    Update pantry item location and remember it per item name.
    """
    location = (location or "Ukategoriseret").strip() or "Ukategoriseret"
    text_key = (text or "").strip().lower()

    with _conn() as con:
        cur = con.cursor()

        cur.execute(
            "UPDATE pantry_items SET location=? WHERE uid=?",
            (location, uid),
        )

        if text_key:
            cur.execute(
                "INSERT INTO pantry_location_memory (text_key, location) VALUES (?, ?) "
                "ON CONFLICT(text_key) DO UPDATE SET location=excluded.location",
                (text_key, location),
            )

        con.commit()


def pantry_get(uid: str) -> Optional[Tuple[str, float, str]]:
    with _conn() as con:
        row = con.execute(
            "SELECT text, qty, location FROM pantry_items WHERE uid=?",
            (uid,),
        ).fetchone()
    if not row:
        return None
    return (row[0], float(row[1]), row[2])


def pantry_used_add_back(uid: str, qty_used: float) -> Optional[str]:
    """
    When user taps "Brugt":
      - subtract qty_used from pantry item
      - delete row if qty <= 0
      - return item text (so UI can add to shopping)
    """
    if qty_used <= 0:
        qty_used = 1.0

    with _conn() as con:
        cur = con.cursor()

        row = cur.execute(
            "SELECT text, qty FROM pantry_items WHERE uid=?",
            (uid,),
        ).fetchone()
        if not row:
            return None

        text, qty = row
        remaining = float(qty) - float(qty_used)

        if remaining > 0:
            cur.execute(
                "UPDATE pantry_items SET qty=? WHERE uid=?",
                (remaining, uid),
            )
        else:
            cur.execute("DELETE FROM pantry_items WHERE uid=?", (uid,))

        con.commit()
        return text
