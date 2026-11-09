# fsaudit

Outil en ligne de commande : on scanne un dossier, les fichiers sont enregistrés
dans une base SQLite, puis on analyse (doublons, différences, plus gros fichiers).

## Installation

```bash
# Dossier du venv hors du dossier synchronisé (iCloud duplique les fichiers du venv)
export UV_PROJECT_ENVIRONMENT="$HOME/.venvs/fsaudit"
uv sync --no-editable   # à relancer après chaque modification du code
```

Toutes les commandes se lancent avec `uv run fsaudit ...` (pas besoin d'activer le venv).

## Utilisation

```bash
uv run fsaudit scan <dossier> --exclude "*.jpg" --exclude ".git"   # enregistrer un scan
uv run fsaudit dupes                                               # doublons + espace récupérable
uv run fsaudit diff                                                # ajouté / supprimé / modifié / déplacé
uv run fsaudit top --count 10                                      # plus gros fichiers + taille par extension
```


- `--include "*.py"` : ne garder que certains fichiers.
- Les erreurs (fichier illisible, permission refusée) sont loggées, le scan continue.
- `diff` compare les deux derniers scans **du même dossier**.
- `dupes`, `diff` et `top` travaillent sur le dernier scan.
- La base `fsaudit.db` est créée **dans le dossier où tu lances la commande** : lance toujours `scan`, `dupes`, `diff` et `top` depuis le même dossier.

## Configuration

Trois variables d'environnement, avec une valeur par défaut :

| Variable             | Défaut        | Rôle            |
|----------------------|---------------|-----------------|
| `FSAUDIT_DB`         | `fsaudit.db`  | base SQLite     |
| `FSAUDIT_LOG_FILE`   | `fsaudit.log` | fichier de log  |
| `FSAUDIT_LOG_LEVEL`  | `INFO`        | niveau de log   |

Astuce : ne scanne pas le dossier qui contient `fsaudit.db`, ou exclue-le avec `--exclude "*.db"`.

## Structure

```
src/fsaudit/
  cli.py        commandes (Typer) et logs
  scanner.py    parcours du dossier, hash SHA-256, type MIME
  db.py         base SQLite
  analysis.py   doublons, diff, top
  config.py     configuration (variables d'environnement)
tests/          tests pytest
```

## Qualité

```bash
uv run pytest
uv run mypy
uv run ruff check .
```

## Choix techniques

- **Hash SHA-256 lu par blocs de 1 Mo** : fiable pour détecter les doublons sans charger les gros fichiers en mémoire.
- **Fichiers vides ignorés** pour les doublons et les déplacements (ils ont tous le même hash).
- **Un déplacement** = un fichier disparu et un fichier apparu avec le même contenu.
- **Scan tout ou rien** : les fichiers sont collectés puis enregistrés d'un seul coup, donc un scan interrompu (Ctrl+C) n'écrit rien en base.
- **SQLite** : une base dans un seul fichier, incluse dans Python.
