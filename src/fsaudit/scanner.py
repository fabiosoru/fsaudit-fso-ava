"""Parcours récursif d'un répertoire et indexation en base."""

import fnmatch
import hashlib
import logging
import mimetypes
import os
import sqlite3
from pathlib import Path

from fsaudit.db import FileRecord, create_scan, delete_scan, finish_scan, insert_file

logger = logging.getLogger("fsaudit")


def file_hash(path: Path) -> str:
    """SHA-256 du fichier, lu par blocs pour ne pas saturer la mémoire."""
    sha = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(1024 * 1024):
            sha.update(chunk)
    return sha.hexdigest()


def is_excluded(name: str, excludes: list[str]) -> bool:
    return any(fnmatch.fnmatch(name, pattern) for pattern in excludes)


def is_included(name: str, includes: list[str]) -> bool:
    """Sans pattern --include, tout est inclus."""
    return not includes or any(fnmatch.fnmatch(name, p) for p in includes)


def build_record(path: Path) -> FileRecord:
    stat = path.stat()
    mime, _ = mimetypes.guess_type(path.name)
    return FileRecord(
        path=str(path),
        size=stat.st_size,
        mtime=stat.st_mtime,
        extension=path.suffix.lower(),
        mime=mime or "application/octet-stream",
        hash=file_hash(path),
    )


def scan(
    conn: sqlite3.Connection,
    root: Path,
    excludes: list[str] | None = None,
    includes: list[str] | None = None,
    skip: set[Path] | None = None,
) -> tuple[int, int, int]:
    """Scanne `root`. Renvoie (id du scan, nb fichiers indexés, nb erreurs).

    `skip` : fichiers à ignorer (ex : la base et le log de fsaudit lui-même).
    """
    excludes = excludes or []
    includes = includes or []
    skip = {p.resolve() for p in (skip or set())}
    scan_id = create_scan(conn, str(root))
    indexed = 0
    errors = 0

    def on_walk_error(err: OSError) -> None:
        nonlocal errors
        errors += 1
        logger.error("Impossible de lire le dossier : %s", err)

    try:
        for dirpath, dirnames, filenames in os.walk(root, onerror=on_walk_error):
            # On retire les dossiers exclus pour ne pas y descendre
            dirnames[:] = [d for d in dirnames if not is_excluded(d, excludes)]

            for name in filenames:
                if is_excluded(name, excludes) or not is_included(name, includes):
                    continue
                path = Path(dirpath) / name
                if path.resolve() in skip:
                    continue
                try:
                    insert_file(conn, scan_id, build_record(path))
                    indexed += 1
                    if indexed % 1000 == 0:
                        logger.info("%d fichiers indexés...", indexed)
                except OSError as err:  # permission refusée, fichier disparu...
                    errors += 1
                    logger.error("Fichier ignoré %s : %s", path, err)

    except BaseException:  # Ctrl+C ou erreur grave : on ne garde rien
        delete_scan(conn, scan_id)
        raise

    finish_scan(conn, scan_id)
    logger.info("Scan %d terminé : %d fichiers, %d erreurs", scan_id, indexed, errors)
    return scan_id, indexed, errors
