"""Parcourt un dossier et renvoie la liste des fichiers trouvés."""

import fnmatch
import hashlib
import logging
import mimetypes
import os
from pathlib import Path

from fsaudit.db import FileRecord

logger = logging.getLogger("fsaudit")


def file_hash(path: Path) -> str:
    """Empreinte SHA-256, lue par morceaux de 1 Mo pour ne pas saturer la mémoire."""
    sha = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            sha.update(chunk)
    return sha.hexdigest()


def scan(
    root: Path, excludes: list[str], includes: list[str]
) -> tuple[list[FileRecord], int]:
    """Renvoie (fichiers trouvés, nombre d'erreurs)."""
    files: list[FileRecord] = []
    errors = 0

    for dirpath, dirnames, filenames in os.walk(root, onerror=_log_folder_error):
        dirnames[:] = [d for d in dirnames if not _matches(d, excludes)]
        for name in filenames:
            if _matches(name, excludes):
                continue
            if includes and not _matches(name, includes):
                continue
            path = Path(dirpath) / name
            try:
                stat = path.stat()
                files.append(
                    FileRecord(
                        path=str(path),
                        size=stat.st_size,
                        mtime=stat.st_mtime,
                        extension=path.suffix.lower(),
                        mime=mimetypes.guess_type(name)[0]
                        or "application/octet-stream",
                        hash=file_hash(path),
                    )
                )
            except OSError as err:  # permission refusée, fichier disparu...
                errors += 1
                logger.error("Fichier ignoré %s : %s", path, err)

    return files, errors


def _matches(name: str, patterns: list[str]) -> bool:
    """Vrai si le nom correspond à un des motifs, par exemple '*.jpg'."""
    return any(fnmatch.fnmatch(name, pattern) for pattern in patterns)


def _log_folder_error(err: OSError) -> None:
    logger.error("Dossier illisible : %s", err)
