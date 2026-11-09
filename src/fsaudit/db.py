"""Base SQLite : on enregistre chaque scan avec la liste de ses fichiers."""

import sqlite3
from dataclasses import dataclass


@dataclass
class FileRecord:
    """Les informations d'un fichier, telles qu'enregistrées en base."""

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
    """Enregistre un scan avec tous ses fichiers. Renvoie l'id du scan."""
    cur = conn.execute("INSERT INTO scans (root) VALUES (?)", (root,))
    scan_id = int(cur.lastrowid or 0)
    for f in files:
        conn.execute(
            "INSERT INTO files VALUES (?, ?, ?, ?, ?, ?, ?)",
            (scan_id, f.path, f.size, f.mtime, f.extension, f.mime, f.hash),
        )
    conn.commit()
    return scan_id


def load_files(conn: sqlite3.Connection, scan_id: int) -> list[FileRecord]:
    """Relit tous les fichiers d'un scan."""
    rows = conn.execute(
        "SELECT path, size, mtime, extension, mime, hash FROM files WHERE scan_id = ?",
        (scan_id,),
    ).fetchall()
    return [FileRecord(*row) for row in rows]


def last_scan(conn: sqlite3.Connection) -> int | None:
    """Id du dernier scan, ou None si la base est vide."""
    row = conn.execute("SELECT MAX(id) FROM scans").fetchone()
    return None if row[0] is None else int(row[0])


def previous_scan(conn: sqlite3.Connection, scan_id: int) -> int | None:
    """Id du scan précédent, pour le même dossier. None s'il n'y en a pas."""
    row = conn.execute(
        "SELECT id FROM scans WHERE id < ? AND root = "
        "(SELECT root FROM scans WHERE id = ?) ORDER BY id DESC LIMIT 1",
        (scan_id, scan_id),
    ).fetchone()
    return row[0] if row else None
