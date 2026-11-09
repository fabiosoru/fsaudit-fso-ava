import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from fsaudit import scanner
from fsaudit.analysis import diff_scans, find_duplicates, size_by_extension
from fsaudit.cli import app
from fsaudit.config import load_config
from fsaudit.db import (
    FileRecord,
    connect,
    get_files,
    latest_scan,
    two_latest_scans_same_root,
)
from fsaudit.scanner import scan


def rec(path: str, hash: str, size: int = 10, ext: str = ".txt") -> FileRecord:
    return FileRecord(path, size, 0.0, ext, "text/plain", hash)


def make_tree(root: Path) -> None:
    (root / "sub").mkdir()
    (root / "a.txt").write_text("hello")
    (root / "sub" / "b.txt").write_text("hello")  # doublon de a.txt
    (root / "c.jpg").write_text("image")
    (root / "sub" / ".git").mkdir()
    (root / "sub" / ".git" / "x").write_text("secret")


def test_scan_et_exclusion(tmp_path: Path) -> None:
    make_tree(tmp_path)
    conn = connect(str(tmp_path / "t.db"))
    scan_id, indexed, errors = scan(conn, tmp_path, excludes=["*.jpg", ".git", "*.db"])
    names = {Path(f.path).name for f in get_files(conn, scan_id)}
    assert names == {"a.txt", "b.txt"}
    assert indexed == 2
    assert errors == 0


def test_scan_include(tmp_path: Path) -> None:
    make_tree(tmp_path)
    conn = connect(str(tmp_path / "t.db"))
    scan_id, _, _ = scan(conn, tmp_path, includes=["*.jpg"])
    assert [Path(f.path).name for f in get_files(conn, scan_id)] == ["c.jpg"]


def test_doublons() -> None:
    files = [rec("a", "h1", 100), rec("b", "h1", 100), rec("c", "h2")]
    groups = find_duplicates(files)
    assert len(groups) == 1
    assert {f.path for f in groups[0]} == {"a", "b"}


def test_diff() -> None:
    old = [rec("a", "1"), rec("b", "2"), rec("c", "3"), rec("d", "4")]
    new = [rec("a", "1"), rec("b", "22"), rec("e", "3"), rec("f", "5")]
    result = diff_scans(old, new)
    assert result.added == ["f"]
    assert result.removed == ["d"]
    assert result.modified == ["b"]
    assert result.moved == [("c", "e")]


def test_taille_par_extension() -> None:
    files = [
        rec("a", "1", 5, ".txt"),
        rec("b", "2", 7, ".txt"),
        rec("c", "3", 1, ".py"),
    ]
    assert size_by_extension(files) == {".txt": 12, ".py": 1}


def test_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data = tmp_path / "data"
    data.mkdir()
    make_tree(data)
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()

    result = runner.invoke(
        app, ["scan", str(data), "--exclude", "*.jpg", "--exclude", ".git"]
    )
    assert result.exit_code == 0
    assert "2 fichiers" in result.output

    result = runner.invoke(app, ["dupes"])
    assert result.exit_code == 0
    assert "2 copies" in result.output

    result = runner.invoke(app, ["top"])
    assert result.exit_code == 0
    assert ".txt" in result.output


def test_fichiers_vides_ne_sont_pas_des_doublons() -> None:
    files = [rec("a", "vide", 0), rec("b", "vide", 0)]
    assert find_duplicates(files) == []
    result = diff_scans([rec("a", "vide", 0)], [rec("b", "vide", 0)])
    assert result.moved == []
    assert result.added == ["b"]
    assert result.removed == ["a"]


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
    conn = connect(str(tmp_path / "t.db"))
    _, indexed, errors = scan(conn, tmp_path, excludes=[".git", "*.db"])
    assert errors == 1
    assert indexed == 2  # b.txt et c.jpg


def test_scan_interrompu_nest_pas_garde(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    make_tree(tmp_path)

    def boom(path: Path) -> str:
        raise KeyboardInterrupt

    monkeypatch.setattr(scanner, "file_hash", boom)
    conn = connect(str(tmp_path / "t.db"))
    with pytest.raises(KeyboardInterrupt):
        scan(conn, tmp_path)
    assert latest_scan(conn) is None
    assert conn.execute("SELECT COUNT(*) FROM scans").fetchone()[0] == 0


def test_scan_ne_sindexe_pas_lui_meme(tmp_path: Path) -> None:
    data = tmp_path / "data"
    data.mkdir()
    (data / "a.txt").write_text("x")
    db_file = data / "fsaudit.db"
    conn = connect(str(db_file))
    scan_id, _, _ = scan(conn, data, skip={db_file})
    assert [Path(f.path).name for f in get_files(conn, scan_id)] == ["a.txt"]


def test_diff_ignore_les_scans_dun_autre_dossier(tmp_path: Path) -> None:
    conn = connect(str(tmp_path / "t.db"))
    for name in ("un", "deux"):
        (tmp_path / name).mkdir()
        (tmp_path / name / "f.txt").write_text(name)
    scan(conn, tmp_path / "un")
    assert two_latest_scans_same_root(conn) is None
    scan(conn, tmp_path / "deux")
    assert two_latest_scans_same_root(conn) is None  # racines différentes
    scan(conn, tmp_path / "un")
    assert two_latest_scans_same_root(conn) == (1, 3)


def test_config_fichier_json_puis_env(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / "fsaudit.json").write_text('{"db_path": "a.db", "log_level": "DEBUG"}')
    config = load_config()
    assert (config.db_path, config.log_level) == ("a.db", "DEBUG")
    monkeypatch.setenv("FSAUDIT_DB", "env.db")
    assert load_config().db_path == "env.db"


def test_cli_json_et_diff(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    data = tmp_path / "data"
    data.mkdir()
    (data / "a.txt").write_text("hello")
    monkeypatch.chdir(tmp_path)
    runner = CliRunner()
    assert runner.invoke(app, ["scan", str(data)]).exit_code == 0
    (data / "b.txt").write_text("nouveau")
    assert runner.invoke(app, ["scan", str(data)]).exit_code == 0

    result = runner.invoke(app, ["diff", "--json"])
    assert result.exit_code == 0
    parsed = json.loads(result.output[result.output.index("{") :])
    assert parsed["added"] == [str(data / "b.txt")]
    assert runner.invoke(app, ["scan", str(tmp_path / "absent")]).exit_code == 1
