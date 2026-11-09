"""Analyses : doublons, diff entre scans, top des fichiers."""

from collections import defaultdict
from dataclasses import dataclass, field

from fsaudit.db import FileRecord


def find_duplicates(files: list[FileRecord]) -> list[list[FileRecord]]:
    """Groupes de fichiers au contenu identique (même hash), le plus lourd d'abord."""
    by_hash: dict[str, list[FileRecord]] = defaultdict(list)
    for f in files:
        if f.size > 0:  # fichiers vides : même hash, pas de vrais doublons
            by_hash[f.hash].append(f)
    groups = [g for g in by_hash.values() if len(g) > 1]
    groups.sort(key=wasted_space, reverse=True)
    return groups


def wasted_space(group: list[FileRecord]) -> int:
    """Espace récupérable : on garde un exemplaire, on supprime les autres."""
    return group[0].size * (len(group) - 1)


@dataclass
class DiffResult:
    added: list[str] = field(default_factory=list)
    removed: list[str] = field(default_factory=list)
    modified: list[str] = field(default_factory=list)
    moved: list[tuple[str, str]] = field(default_factory=list)


def diff_scans(old: list[FileRecord], new: list[FileRecord]) -> DiffResult:
    old_by_path = {f.path: f for f in old}
    new_by_path = {f.path: f for f in new}
    result = DiffResult()

    added = [f for p, f in new_by_path.items() if p not in old_by_path]
    removed = [f for p, f in old_by_path.items() if p not in new_by_path]

    for path, new_file in new_by_path.items():
        old_file = old_by_path.get(path)
        if old_file is not None and old_file.hash != new_file.hash:
            result.modified.append(path)

    # Déplacé = supprimé à un endroit et ajouté ailleurs avec le même contenu
    removed_by_hash: dict[str, list[FileRecord]] = defaultdict(list)
    for f in removed:
        if f.size == 0:  # un fichier vide ne peut pas être déplacé de façon fiable
            result.removed.append(f.path)
            continue
        removed_by_hash[f.hash].append(f)

    for f in added:
        candidates = removed_by_hash.get(f.hash) if f.size > 0 else None
        if candidates:
            origin = candidates.pop()
            result.moved.append((origin.path, f.path))
        else:
            result.added.append(f.path)

    result.removed += [f.path for fl in removed_by_hash.values() for f in fl]
    return result


def top_largest(files: list[FileRecord], count: int) -> list[FileRecord]:
    return sorted(files, key=lambda f: f.size, reverse=True)[:count]


def size_by_extension(files: list[FileRecord]) -> dict[str, int]:
    """Taille totale par extension, de la plus grosse à la plus petite."""
    totals: dict[str, int] = defaultdict(int)
    for f in files:
        totals[f.extension or "(aucune)"] += f.size
    return dict(sorted(totals.items(), key=lambda item: item[1], reverse=True))
