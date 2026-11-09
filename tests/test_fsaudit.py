from pathlib import Path

import pytest
from typer.testing import CliRunner

from fsaudit import scanner
from fsaudit.analysis import diff_scans, find_duplicates
from fsaudit.cli import app
from fsaudit.db import FileRecord


def rec(path: str, hash: str, size: int = 10) -> FileRecord:
    return FileRecord(path, size, 0.0, ".txt", "text/plain", hash)


def make_tree(root: Path) -> None:
    (root / "sub").mkdir()
    (root / "a.txt").write_text("hello")
    (root / "sub" / "b.txt").write_text("hello")  # doublon de a.txt
    (root / "c.jpg").write_text("image")


def names(files: list[FileRecord]) -> set[str]:
    return {Path(f.path).name for f in files}


def test_scan_exclusions_et_inclusions(tmp_path: Path) -> None:
    make_tree(tmp_path)
    files, errors = scanner.scan(tmp_path, excludes=["*.jpg"], includes=[])
    assert names(files) == {"a.txt", "b.txt"}
    assert errors == 0
    files, _ = scanner.scan(tmp_path, excludes=[], includes=["*.jpg"])
    assert names(files) == {"c.jpg"}


def test_fichier_illisible_ne_plante_pas(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    make_tree(tmp_path)
    real_hash = scanner.file_hash

    def fake_hash(path: Path) -> str:
        if path.name == "a.txt":
            raise PermissionError("refusé")
        return real_hash(path)

    monkeypatch.setattr(scanner, "file_hash", fake_hash)
    files, errors = scanner.scan(tmp_path, excludes=[], includes=[])
    assert errors == 1
    assert names(files) == {"b.txt", "c.jpg"}


def test_doublons_et_fichiers_vides() -> None:
    files = [
        rec("a", "h1"),
        rec("b", "h1"),
        rec("c", "h2"),
        rec("d", "v", 0),
        rec("e", "v", 0),
    ]
    groups = find_duplicates(files)
    assert [{f.path for f in g} for g in groups] == [{"a", "b"}]


def test_diff() -> None:
    old = [rec("a", "1"), rec("b", "2"), rec("c", "3"), rec("d", "4")]
    new = [rec("a", "1"), rec("b", "22"), rec("e", "3"), rec("f", "5")]
    result = diff_scans(old, new)
    assert result.added == ["f"]
    assert result.removed == ["d"]
    assert result.modified == ["b"]
    assert result.moved == [("c", "e")]


def test_cli_de_bout_en_bout(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data = tmp_path / "data"
    data.mkdir()
    make_tree(data)
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    assert runner.invoke(app, ["top"]).exit_code == 1  # aucun scan encore

    result = runner.invoke(app, ["scan", str(data), "--exclude", "*.jpg"])
    assert result.exit_code == 0
    assert "2 fichiers" in result.output

    assert "2 copies" in runner.invoke(app, ["dupes"]).output

    (data / "n.txt").write_text("nouveau")
    (data / "sub" / "b.txt").unlink()
    runner.invoke(app, ["scan", str(data), "--exclude", "*.jpg"])
    diff = runner.invoke(app, ["diff"]).output
    assert "+ ajouté" in diff and "n.txt" in diff
    assert "- supprimé" in diff and "b.txt" in diff

    assert runner.invoke(app, ["scan", str(tmp_path / "absent")]).exit_code == 1
