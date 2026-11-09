"""Calculs sur les fichiers : doublons, différences entre scans, plus gros fichiers."""

from fsaudit.db import FileRecord


def wasted(group: list[FileRecord]) -> int:
    """Octets récupérables : une copie gardée, les autres en trop."""
    return group[0].size * (len(group) - 1)


def duplicates(files: list[FileRecord]) -> list[list[FileRecord]]:
    """Fichiers identiques (même hash), sans les fichiers vides."""
    groups: dict[str, list[FileRecord]] = {}
    for f in files:
        if f.size > 0:
            groups.setdefault(f.hash, []).append(f)

    result = [g for g in groups.values() if len(g) > 1]
    return sorted(result, key=wasted, reverse=True)


def diff(
    old: list[FileRecord], new: list[FileRecord]
) -> tuple[list[str], list[str], list[str], list[tuple[str, str]]]:
    """Compare deux scans. Renvoie (ajoutés, supprimés, modifiés, déplacés)."""
    old_paths = {f.path: f for f in old}
    new_paths = {f.path: f for f in new}

    # 1. Modifié : même chemin, mais contenu différent
    modified: list[str] = []
    for f in new:
        if f.path in old_paths and old_paths[f.path].hash != f.hash:
            modified.append(f.path)

    # 2. Chemins qui n'existent plus dans le nouveau scan
    gone: list[FileRecord] = []
    for f in old:
        if f.path not in new_paths:
            gone.append(f)

    # 3. Chemins nouveaux : déplacés si un fichier disparu a le même contenu, sinon ajoutés
    added: list[str] = []
    moved: list[tuple[str, str]] = []
    for f in new:
        if f.path in old_paths:
            continue
        found: FileRecord | None = None
        if f.size > 0:  # les fichiers vides ne comptent jamais comme déplacés
            for g in gone:
                if g.hash == f.hash:
                    found = g
                    break
        if found is None:
            added.append(f.path)
        else:
            moved.append((found.path, f.path))
            gone.remove(found)

    # 4. Ce qui n'a pas été retrouvé ailleurs a été supprimé
    removed: list[str] = []
    for g in gone:
        removed.append(g.path)
    return added, removed, modified, moved


def top(files: list[FileRecord], count: int) -> list[FileRecord]:
    """Les `count` fichiers les plus gros."""
    return sorted(files, key=lambda f: f.size, reverse=True)[:count]


def size_by_extension(files: list[FileRecord]) -> dict[str, int]:
    """Taille totale par extension, de la plus grosse à la plus petite."""
    totals: dict[str, int] = {}
    for f in files:
        ext = f.extension or "(aucune)"
        totals[ext] = totals.get(ext, 0) + f.size
    return dict(sorted(totals.items(), key=lambda item: item[1], reverse=True))
