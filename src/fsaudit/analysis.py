"""Analyses : doublons, différences entre deux scans, plus gros fichiers."""

from collections import defaultdict
from dataclasses import dataclass, field

from fsaudit.db import FileRecord


def find_duplicates(files: list[FileRecord]) -> list[list[FileRecord]]:
    """Groupes de fichiers au contenu identique (même hash), les plus gaspilleurs d'abord."""
    by_hash: dict[str, list[FileRecord]] = defaultdict(list)
    for f in files:
        # Les fichiers vides ont tous le même hash : on ne les compte pas
        if f.size > 0:
            by_hash[f.hash].append(f)
    groups = [g for g in by_hash.values() if len(g) > 1]
    return sorted(groups, key=wasted_space, reverse=True)


def wasted_space(group: list[FileRecord]) -> int:
    """Octets récupérables : on garde une copie, on supprime les autres."""
    return group[0].size * (len(group) - 1)


@dataclass
class DiffResult:
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    modified: list[str] = field(default_factory=list)
    moved: list[tuple[str, str]] = field(default_factory=list)


def diff_scans(old: list[FileRecord], new: list[FileRecord]) -> DiffResult:
    """Compare deux scans du même dossier."""
    old_by_path = {f.path: f for f in old}
    new_by_path = {f.path: f for f in new}
    result = DiffResult()

    # Même chemin dans les deux scans : modifié si le contenu a changé
    for path, f in new_by_path.items():
        if path in old_by_path and old_by_path[path].hash != f.hash:
            result.modified.append(path)

    # Chemins qui ont disparu, rangés par hash pour repérer les déplacements
    gone_by_hash: dict[str, list[str]] = defaultdict(list)
    for path, f in old_by_path.items():
        if path not in new_by_path:
            if f.size > 0:
                gone_by_hash[f.hash].append(path)
            else:
                result.removed.append(path)

    # Chemins apparus : déplacés si un chemin disparu a le même contenu, sinon ajoutés
    for path, f in new_by_path.items():
        if path in old_by_path:
            continue
        sources = gone_by_hash.get(f.hash) if f.size > 0 else None
        if sources:
            result.moved.append((sources.pop(), path))
        else:
            result.added.append(path)

    # Ce qui n'a pas de destination est supprimé
    for paths in gone_by_hash.values():
        result.removed.extend(paths)
    return result


def top_largest(files: list[FileRecord], count: int) -> list[FileRecord]:
    """Les `count` fichiers les plus lourds."""
    return sorted(files, key=lambda f: f.size, reverse=True)[:count]


def size_by_extension(files: list[FileRecord]) -> dict[str, int]:
    """Taille totale par extension, de la plus grosse à la plus petite."""
    totals: dict[str, int] = defaultdict(int)
    for f in files:
        totals[f.extension or "(aucune)"] += f.size
    return dict(sorted(totals.items(), key=lambda item: item[1], reverse=True))
