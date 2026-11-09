# fsaudit

Outil d'audit de fichiers en ligne de commande : on scanne un dossier, tout est
indexé dans une base SQLite, puis on analyse (doublons, différences, plus gros fichiers).

## Installation

```bash
uv sync
```

## Utilisation

```bash
uv run fsaudit scan <dossier> --exclude "*.jpg" --exclude ".git"   # indexer
uv run fsaudit dupes                                               # doublons + espace récupérable
uv run fsaudit diff                                                # ajouté / supprimé / modifié / déplacé
uv run fsaudit top --count 10                                      # plus gros fichiers + taille par extension
```

- `--include "*.py"` : n'indexer que certains fichiers.
- Les erreurs (fichier illisible, permission refusée) sont loggées et le scan continue.
- Un scan interrompu (Ctrl+C) n'est pas conservé.
- `diff` compare les deux derniers scans **du même dossier**.
- `dupes` et `top` analysent le dernier scan.

### Extension : sortie `--json`

`dupes`, `diff` et `top` acceptent `--json`. Le résultat est exploitable par
d'autres outils (`jq`, scripts, tableaux de bord) sans parser du texte.

```bash
uv run fsaudit dupes --json | jq .total_recoverable_bytes
```

Justification : un outil CLI est plus utile s'il se branche sur d'autres outils.
JSON est un format standard, lisible, et ça ne demande que `json` de la stdlib :
pas de dépendance en plus.

## Configuration

Valeurs par défaut, surchargées par `fsaudit.json` (dossier courant), puis par
les variables d'environnement.

| Option      | JSON        | Variable d'environnement | Défaut        |
|-------------|-------------|--------------------------|---------------|
| Base SQLite | `db_path`   | `FSAUDIT_DB`             | `fsaudit.db`  |
| Fichier log | `log_file`  | `FSAUDIT_LOG_FILE`       | `fsaudit.log` |
| Niveau log  | `log_level` | `FSAUDIT_LOG_LEVEL`      | `INFO`        |

## Structure

```
src/fsaudit/
  cli.py        commandes (Typer)
  scanner.py    parcours récursif, hash, MIME, include/exclude
  db.py         base SQLite
  analysis.py   doublons, diff, top
  config.py     configuration
  log.py        logs console + fichier
tests/          tests pytest
```

## Qualité

```bash
uv run pytest
uv run mypy
uv run ruff check .
```

## Choix techniques

- **Hash SHA-256 lu par blocs de 1 Mo** : fiable pour détecter les doublons sans
  charger de gros fichiers en mémoire.
- **Fichiers vides ignorés** pour les doublons et les déplacements (ils ont tous le même hash).
- **Un déplacement** = un fichier supprimé et un fichier ajouté avec le même contenu.
- **SQLite** : base unique en un fichier, dans la bibliothèque standard.
