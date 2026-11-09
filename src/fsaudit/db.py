"""Base SQLite : une table pour les scans, une table pour les fichiers."""

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


def connect(db_path: str) -> sqlite3.Connection:
    """Ouvre la base et crée les tables si elles n'existent pas."""
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE IF NOT EXISTS scans (id INTEGER PRIMARY KEY, root TEXT)")
    conn.execute(
        "CREATE TABLE IF NOT EXISTS files (scan_id INTEGER, path TEXT, size INTEGER, "
        "mtime REAL, extension TEXT, mime TEXT, hash TEXT)"
    )
    return conn


def save_scan(conn: sqlite3.Connection, root: str, files: list[FileRecord]) -> int:
    """Enregistre un scan complet (tous les fichiers d'un coup). Renvoie son id."""
    cur = conn.execute("INSERT INTO scans (root) VALUES (?)", (root,))
    scan_id = int(cur.lastrowid or 0)
    conn.executemany(
        "INSERT INTO files VALUES (?, ?, ?, ?, ?, ?, ?)",
        [
            (scan_id, f.path, f.size, f.mtime, f.extension, f.mime, f.hash)
            for f in files
        ],
    )
    conn.commit()
    return scan_id


def get_files(conn: sqlite3.Connection, scan_id: int) -> list[FileRecord]:
    rows = conn.execute(
        "SELECT path, size, mtime, extension, mime, hash FROM files WHERE scan_id = ?",
        (scan_id,),
    ).fetchall()
    return [FileRecord(*row) for row in rows]


def latest_scan(conn: sqlite3.Connection) -> int | None:
    row = conn.execute("SELECT MAX(id) FROM scans").fetchone()
    return row[0] if row else None


def previous_scan(conn: sqlite3.Connection, scan_id: int) -> int | None:
    """Le scan précédent du MÊME dossier, ou None."""
    row = conn.execute(
        "SELECT id FROM scans WHERE root = (SELECT root FROM scans WHERE id = ?) "
        "AND id < ? ORDER BY id DESC LIMIT 1",
        (scan_id, scan_id),
    ).fetchone()
    return row[0] if row else None
