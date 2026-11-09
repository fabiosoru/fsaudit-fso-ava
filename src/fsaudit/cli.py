"""Commandes : fsaudit scan | dupes | diff | top."""

import logging
import sqlite3
from pathlib import Path
from typing import Annotated

import typer

from fsaudit import analysis, config, db
from fsaudit.scanner import scan

app = typer.Typer(help="Outil d'audit de fichiers.")


@app.callback()
def setup() -> None:
    """Avant chaque commande : les logs vont dans la console et dans fsaudit.log."""
    logging.basicConfig(
        level=config.LOG_LEVEL,
        format="%(asctime)s %(levelname)s %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler(config.LOG_FILE, encoding="utf-8"),
        ],
    )


@app.command("scan")
def scan_cmd(
    root: Annotated[Path, typer.Argument(help="Dossier à scanner")],
    exclude: Annotated[list[str] | None, typer.Option(help="Motif à exclure")] = None,
    include: Annotated[list[str] | None, typer.Option(help="Motif à inclure")] = None,
) -> None:
    """Scanne un dossier et l'enregistre en base."""
    if not root.is_dir():
        typer.echo(f"{root} n'est pas un dossier.")
        raise typer.Exit(code=1)

    folder = root.resolve()
    files, errors = scan(folder, exclude or [], include or [])
    scan_id = db.save_scan(db.connect(config.DB_PATH), str(folder), files)
    typer.echo(f"Scan {scan_id} : {len(files)} fichiers, {errors} erreurs.")


@app.command()
def dupes() -> None:
    """Doublons et espace récupérable (dernier scan)."""
    conn = db.connect(config.DB_PATH)
    groups = analysis.duplicates(db.load_files(conn, _last(conn)))

    for group in groups:
        typer.echo(f"\n{len(group)} copies, {analysis.wasted(group)} octets :")
        for f in group:
            typer.echo(f"  {f.path}")
    total = sum(analysis.wasted(g) for g in groups)
    typer.echo(f"\nTotal récupérable : {total} octets")


@app.command()
def diff() -> None:
    """Compare les deux derniers scans d'un même dossier."""
    conn = db.connect(config.DB_PATH)
    new_id = _last(conn)
    old_id = db.previous_scan(conn, new_id)
    if old_id is None:
        typer.echo("Il faut deux scans du même dossier pour faire un diff.")
        raise typer.Exit(code=1)

    added, removed, modified, moved = analysis.diff(
        db.load_files(conn, old_id), db.load_files(conn, new_id)
    )
    for path in added:
        typer.echo(f"+ ajouté    {path}")
    for path in removed:
        typer.echo(f"- supprimé  {path}")
    for path in modified:
        typer.echo(f"~ modifié   {path}")
    for src, dst in moved:
        typer.echo(f"> déplacé   {src} -> {dst}")


@app.command()
def top(count: Annotated[int, typer.Option(help="Nombre de fichiers")] = 10) -> None:
    """Plus gros fichiers et taille par extension (dernier scan)."""
    conn = db.connect(config.DB_PATH)
    files = db.load_files(conn, _last(conn))

    typer.echo(f"Top {count} des fichiers :")
    for f in analysis.top(files, count):
        typer.echo(f"  {f.size:>12}  {f.path}")
    typer.echo("\nTaille par extension :")
    for ext, size in analysis.size_by_extension(files).items():
        typer.echo(f"  {ext:<10} {size:>12}")


def _last(conn: sqlite3.Connection) -> int:
    """Id du dernier scan. Arrête la commande si la base est vide."""
    scan_id = db.last_scan(conn)
    if scan_id is None:
        typer.echo("Aucun scan en base. Lancez d'abord : fsaudit scan <dossier>")
        raise typer.Exit(code=1)
    return scan_id
