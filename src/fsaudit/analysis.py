"""Analyses : doublons, différences entre deux scans, plus gros fichiers."""

from fsaudit.db import FileRecord


def wasted_space(group: list[FileRecord]) -> int:
    """Octets récupérables dans un groupe de doublons.

    On garde une copie et on supprime les autres :
    3 copies de 100 octets -> 200 octets récupérables.
    """
    return group[0].size * (len(group) - 1)


def find_duplicates(files: list[FileRecord]) -> list[list[FileRecord]]:
    """Trouve les groupes de fichiers qui ont le même contenu (même hash)."""
    # On range les fichiers par hash : {hash: [fichier, fichier, ...]}
    groups_by_hash: dict[str, list[FileRecord]] = {}
    for f in files:
        if f.size == 0:
            continue  # les fichiers vides ont tous le même hash : pas de vrais doublons
        if f.hash not in groups_by_hash:
            groups_by_hash[f.hash] = []
        groups_by_hash[f.hash].append(f)

    # Un doublon = un hash qui a au moins 2 fichiers
    duplicates: list[list[FileRecord]] = []
    for group in groups_by_hash.values():
        if len(group) >= 2:
            duplicates.append(group)

    # Les groupes qui font gagner le plus de place en premier
    duplicates.sort(key=wasted_space, reverse=True)
    return duplicates


class DiffResult:
    """Le résultat d'un diff : 4 listes."""

    def __init__(self) -> None:
        self.added: list[str] = []  # chemins ajoutés
        self.removed: list[str] = []  # chemins supprimés
        self.modified: list[str] = []  # chemins dont le contenu a changé
        self.moved: list[tuple[str, str]] = []  # (ancien chemin, nouveau chemin)


def diff_scans(old: list[FileRecord], new: list[FileRecord]) -> DiffResult:
    """Compare l'ancien scan et le nouveau scan d'un même dossier."""
    result = DiffResult()

    # On retrouve chaque fichier à partir de son chemin : {chemin: fiche}
    old_by_path: dict[str, FileRecord] = {}
    for f in old:
        old_by_path[f.path] = f
    new_by_path: dict[str, FileRecord] = {}
    for f in new:
        new_by_path[f.path] = f

    # 1. Modifié : même chemin dans les deux scans, mais contenu différent
    for path, new_file in new_by_path.items():
        if path in old_by_path and old_by_path[path].hash != new_file.hash:
            result.modified.append(path)

    # 2. Disparus : chemins de l'ancien scan qui ne sont plus dans le nouveau
    disappeared: list[FileRecord] = []
    for path, old_file in old_by_path.items():
        if path not in new_by_path:
            disappeared.append(old_file)

    # 3. Apparus : chemins du nouveau scan qui n'étaient pas dans l'ancien
    appeared: list[FileRecord] = []
    for path, new_file in new_by_path.items():
        if path not in old_by_path:
            appeared.append(new_file)

    # 4. Pour chaque apparu, on cherche un disparu avec le même contenu :
    #    si on en trouve un, le fichier a été déplacé. Sinon, il est ajouté.
    for new_file in appeared:
        origin: FileRecord | None = None
        if new_file.size > 0:  # on ignore les fichiers vides
            for old_file in disappeared:
                if old_file.hash == new_file.hash:
                    origin = old_file
                    break
        if origin is not None:
            result.moved.append((origin.path, new_file.path))
            disappeared.remove(origin)  # ce fichier est déjà expliqué
        else:
            result.added.append(new_file.path)

    # 5. Les disparus qui n'ont pas été déplacés ont été supprimés
    for old_file in disappeared:
        result.removed.append(old_file.path)

    return result


def file_size(f: FileRecord) -> int:
    """Renvoie la taille d'un fichier (sert à trier)."""
    return f.size


def top_largest(files: list[FileRecord], count: int) -> list[FileRecord]:
    """Les `count` fichiers les plus gros."""
    sorted_files = sorted(files, key=file_size, reverse=True)
    return sorted_files[:count]  # les `count` premiers


def second_item(pair: tuple[str, int]) -> int:
    """Renvoie le 2e élément d'un couple (extension, taille) : sert à trier."""
    return pair[1]


def size_by_extension(files: list[FileRecord]) -> dict[str, int]:
    """Taille totale par extension, de la plus grosse à la plus petite."""
    totals: dict[str, int] = {}
    for f in files:
        extension = f.extension
        if extension == "":
            extension = "(aucune)"
        if extension not in totals:
            totals[extension] = 0
        totals[extension] += f.size

    sorted_pairs = sorted(totals.items(), key=second_item, reverse=True)
    return dict(sorted_pairs)
