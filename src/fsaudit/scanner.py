import fnmatch
import hashlib
import logging
import mimetypes
import os
from pathlib import Path

from fsaudit.db import FileRecord

logger = logging.getLogger("fsaudit")


def file_hash(path: Path) -> str:
    #Cette fonction permet de définir le hash d'un fichier, on le parcours que 1mo par 1mo pour ne pas saturer la mémoire
    sha = hashlib.sha256()
    with path.open("rb") as f:
        while True:
            morceau = f.read(1024 * 1024)
            if morceau == b"":
                break
            sha.update(morceau)
    return sha.hexdigest()


def matches(name: str, patterns: list[str]) -> bool:
    #On identifie l'extension du fichier puis on retourne un booléen quand c'est true on est sur la bonne
    for pattern in patterns:
        if fnmatch.fnmatch(name, pattern):
            return True
    return False


def make_record(path: Path) -> FileRecord:
    """Crée la fiche d'un fichier (peut lever OSError si le fichier est illisible)."""
    stat = path.stat()
    mime, _ = mimetypes.guess_type(path.name)
    if mime is None:
        mime = "application/octet-stream"  # type inconnu
    return FileRecord(
        path=str(path),
        size=stat.st_size,
        mtime=stat.st_mtime,
        extension=path.suffix.lower(),
        mime=mime,
        hash=file_hash(path),
    )


def scan(
    root: Path, excludes: list[str], includes: list[str]
) -> tuple[list[FileRecord], int]:
    """Parcourt `root` et renvoie (liste des fiches, nombre d'erreurs)."""
    files: list[FileRecord] = []
    errors = 0

    # os.walk visite le dossier, puis ses sous-dossiers, etc.
    for dirpath, dirnames, filenames in os.walk(root, onerror=log_folder_error):
        # On retire les sous-dossiers exclus : os.walk n'ira pas dedans
        for dirname in list(dirnames):
            if matches(dirname, excludes):
                dirnames.remove(dirname)

        for name in filenames:
            if matches(name, excludes):
                continue  # fichier exclu : on passe au suivant
            if len(includes) > 0 and not matches(name, includes):
                continue  # on veut seulement certains fichiers, pas celui-ci

            path = Path(dirpath) / name
            try:
                files.append(make_record(path))
            except PermissionError:
                errors += 1
                logger.error("Permission refusée, fichier ignoré : %s", path)
            except FileNotFoundError:
                errors += 1
                logger.error("Fichier disparu pendant le scan : %s", path)
            except OSError as err:  # autre problème de lecture (disque, réseau...)
                errors += 1
                logger.error("Erreur de lecture, fichier ignoré %s : %s", path, err)

    return files, errors


def log_folder_error(err: OSError) -> None:
    # Appelée par os.walk quand un dossier est illisible.
    if isinstance(err, PermissionError):
        logger.error("Permission refusée, dossier ignoré : %s", err.filename)
    elif isinstance(err, FileNotFoundError):
        logger.error("Dossier disparu pendant le scan : %s", err.filename)
    else:
        logger.error("Dossier illisible : %s", err)
