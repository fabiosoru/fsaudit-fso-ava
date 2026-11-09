"""Accès à la base SQLite."""

import sqlite3
from dataclasses import dataclass


@dataclass
class FileRecord:
    path: str
    size: int
    mtime: float
    extension: str
    mime: str
    hash: str


SCHEMA = """
CREATE TABLE IF NOT EXISTS scans (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    root TEXT NOT NULL,
    date TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    finished INTEGER NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS files (
    scan_id INTEGER NOT NULL REFERENCES scans(id),
    path TEXT NOT NULL,
    size INTEGER NOT NULL,
    mtime REAL NOT NULL,
    extension TEXT NOT NULL,
    mime TEXT NOT NULL,
    hash TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_files_scan ON files(scan_id);
"""


def connect(db_path: str) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.executescript(SCHEMA)
    return conn


def create_scan(conn: sqlite3.Connection, root: str) -> int:
    cur = conn.execute("INSERT INTO scans (root) VALUES (?)", (root,))
    conn.commit()
    assert cur.lastrowid is not None
    return cur.lastrowid


def finish_scan(conn: sqlite3.Connection, scan_id: int) -> None:
    """Marque le scan comme terminé : seuls les scans terminés sont analysés."""
    conn.execute("UPDATE scans SET finished = 1 WHERE id = ?", (scan_id,))
    conn.commit()


def delete_scan(conn: sqlite3.Connection, scan_id: int) -> None:
    """Supprime un scan (utilisé quand il est interrompu)."""
    conn.rollback()
    conn.execute("DELETE FROM files WHERE scan_id = ?", (scan_id,))
    conn.execute("DELETE FROM scans WHERE id = ?", (scan_id,))
    conn.commit()


def insert_file(conn: sqlite3.Connection, scan_id: int, rec: FileRecord) -> None:
    conn.execute(
        "INSERT INTO files VALUES (?, ?, ?, ?, ?, ?, ?)",
        (scan_id, rec.path, rec.size, rec.mtime, rec.extension, rec.mime, rec.hash),
    )


def latest_scan(conn: sqlite3.Connection) -> int | None:
    row = conn.execute(
        "SELECT id FROM scans WHERE finished = 1 ORDER BY id DESC LIMIT 1"
    ).fetchone()
    return int(row[0]) if row else None


def two_latest_scans_same_root(conn: sqlite3.Connection) -> tuple[int, int] | None:
    """(ancien, récent) : le dernier scan et le précédent scan du MÊME dossier."""
    row = conn.execute(
        "SELECT id, root FROM scans WHERE finished = 1 ORDER BY id DESC LIMIT 1"
    ).fetchone()
    if row is None:
        return None
    previous = conn.execute(
        "SELECT id FROM scans WHERE finished = 1 AND root = ? AND id < ? "
        "ORDER BY id DESC LIMIT 1",
        (row[1], row[0]),
    ).fetchone()
    if previous is None:
        return None
    return int(previous[0]), int(row[0])


def get_files(conn: sqlite3.Connection, scan_id: int) -> list[FileRecord]:
    rows = conn.execute(
        "SELECT path, size, mtime, extension, mime, hash FROM files WHERE scan_id = ?",
        (scan_id,),
    ).fetchall()
    return [FileRecord(*r) for r in rows]
