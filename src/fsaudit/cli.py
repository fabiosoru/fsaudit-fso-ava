"""Interface en ligne de commande : fsaudit scan | dupes | diff | top."""

import json
import sqlite3
from dataclasses import asdict
from pathlib import Path
from typing import Annotated

import typer

from fsaudit import analysis, db
from fsaudit.config import load_config
from fsaudit.log import setup_logging
from fsaudit.scanner import scan

app = typer.Typer(help="Outil d'audit de fichiers.")

JsonOption = Annotated[bool, typer.Option("--json", help="Sortie au format JSON")]


@app.callback()
def main() -> None:
    config = load_config()
    setup_logging(config.log_file, config.log_level)


def _open_db() -> sqlite3.Connection:
    return db.connect(load_config().db_path)


def _latest_scan(conn: sqlite3.Connection) -> int:
    scan_id = db.latest_scan(conn)
    if scan_id is None:
        typer.echo("Aucun scan en base. Lancez d'abord : fsaudit scan <dossier>")
        raise typer.Exit(code=1)
    return scan_id


def _print_json(data: object) -> None:
    typer.echo(json.dumps(data, indent=2, ensure_ascii=False))


@app.command("scan")
def scan_cmd(
    root: Annotated[Path, typer.Argument(help="Dossier à scanner")],
    exclude: Annotated[list[str] | None, typer.Option(help="Pattern à exclure")] = None,
    include: Annotated[list[str] | None, typer.Option(help="Pattern à inclure")] = None,
) -> None:
    """Scanne un dossier et l'indexe en base."""
    if not root.is_dir():
        typer.echo(f"{root} n'est pas un dossier.")
        raise typer.Exit(code=1)
    root = root.resolve()  # chemins absolus : le diff marche depuis n'importe où
    config = load_config()
    conn = db.connect(config.db_path)
    # fsaudit ne doit pas s'indexer lui-même (base, journal SQLite et log)
    own_files = {
        Path(config.db_path),
        Path(config.db_path + "-journal"),
        Path(config.log_file),
    }
    scan_id, indexed, errors = scan(conn, root, exclude, include, own_files)
    typer.echo(f"Scan {scan_id} : {indexed} fichiers indexés, {errors} erreurs.")


@app.command()
def dupes(as_json: JsonOption = False) -> None:
    """Liste les doublons et l'espace récupérable."""
    conn = _open_db()
    files = db.get_files(conn, _latest_scan(conn))
    groups = analysis.find_duplicates(files)
    total = sum(analysis.wasted_space(g) for g in groups)

    if as_json:
        _print_json(
            {
                "total_recoverable_bytes": total,
                "groups": [
                    {
                        "wasted_bytes": analysis.wasted_space(g),
                        "files": [f.path for f in g],
                    }
                    for g in groups
                ],
            }
        )
        return

    for group in groups:
        wasted = analysis.wasted_space(group)
        typer.echo(f"\n{len(group)} copies, {wasted} octets récupérables :")
        for f in group:
            typer.echo(f"  {f.path}")
    typer.echo(f"\nTotal récupérable : {total} octets")


@app.command("diff")
def diff_cmd(as_json: JsonOption = False) -> None:
    """Compare les deux derniers scans d'un même dossier."""
    conn = _open_db()
    pair = db.two_latest_scans_same_root(conn)
    if pair is None:
        typer.echo("Il faut deux scans du même dossier pour faire un diff.")
        raise typer.Exit(code=1)
    old, new = db.get_files(conn, pair[0]), db.get_files(conn, pair[1])
    result = analysis.diff_scans(old, new)

    if as_json:
        _print_json(asdict(result))
        return

    for path in result.added:
        typer.echo(f"+ ajouté    {path}")
    for path in result.removed:
        typer.echo(f"- supprimé  {path}")
    for path in result.modified:
        typer.echo(f"~ modifié   {path}")
    for src, dst in result.moved:
        typer.echo(f"> déplacé   {src} -> {dst}")


@app.command()
def top(
    count: Annotated[int, typer.Option(help="Nombre de fichiers")] = 10,
    as_json: JsonOption = False,
) -> None:
    """Fichiers les plus volumineux et répartition par extension."""
    conn = _open_db()
    files = db.get_files(conn, _latest_scan(conn))
    largest = analysis.top_largest(files, count)
    by_ext = analysis.size_by_extension(files)

    if as_json:
        _print_json(
            {
                "largest": [{"path": f.path, "size": f.size} for f in largest],
                "size_by_extension": by_ext,
            }
        )
        return

    typer.echo(f"Top {count} des fichiers :")
    for f in largest:
        typer.echo(f"  {f.size:>12}  {f.path}")
    typer.echo("\nTaille par extension :")
    for ext, size in by_ext.items():
        typer.echo(f"  {ext:<10} {size:>12}")
