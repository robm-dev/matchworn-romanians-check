from datetime import datetime, timezone
from pathlib import Path

import pytest

from mws_monitor.backup_snapshots import current_week_id, run_backup


def _seed_live(repo: Path) -> None:
    (repo / "data").mkdir(parents=True)
    (repo / "outputs" / "u23").mkdir(parents=True)
    (repo / "outputs" / "u21").mkdir(parents=True)
    (repo / "outputs" / "u19").mkdir(parents=True)
    (repo / "data" / "romanian_players.csv").write_text("name\nA\n", encoding="utf-8")
    (repo / "data" / "top_200_u23_players.csv").write_text("name\nB\n", encoding="utf-8")
    (repo / "data" / "top_200_u21_players.csv").write_text("name\nC\n", encoding="utf-8")
    (repo / "data" / "top_200_u19_players.csv").write_text("name\nD\n", encoding="utf-8")
    for folder, tag in [
        (repo / "outputs", "ro"),
        (repo / "outputs" / "u23", "u23"),
        (repo / "outputs" / "u21", "u21"),
        (repo / "outputs" / "u19", "u19"),
    ]:
        (folder / "latest.csv").write_text(f"tag,{tag}\n", encoding="utf-8")
        (folder / "latest.json").write_text("{}", encoding="utf-8")
        (folder / "latest.md").write_text("# x\n", encoding="utf-8")


def test_current_week_id_utc():
    now = datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc)
    assert current_week_id(now) == "2026-W38"


def test_run_backup_writes_main_and_week_without_deleting_prior_week(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    _seed_live(repo)
    backup_root = repo / "backups"

    result_w38 = run_backup(repo, backup_root=backup_root, week_id="2026-W38")
    assert result_w38["week_id"] == "2026-W38"
    assert (backup_root / "main" / "transfermarkt" / "romanian_players.csv").read_text(encoding="utf-8") == "name\nA\n"
    assert (backup_root / "main" / "mws" / "romanian" / "latest.csv").read_text(encoding="utf-8") == "tag,ro\n"
    assert (backup_root / "main" / "mws" / "u23" / "latest.csv").exists()
    assert (backup_root / "weekly" / "2026-W38" / "transfermarkt" / "top_200_u21_players.csv").exists()
    assert len(result_w38["main_copied"]) == 16

    (repo / "data" / "romanian_players.csv").write_text("name\nUPDATED\n", encoding="utf-8")
    run_backup(repo, backup_root=backup_root, week_id="2026-W39")
    assert (backup_root / "weekly" / "2026-W38" / "transfermarkt" / "romanian_players.csv").read_text(encoding="utf-8") == "name\nA\n"
    assert (backup_root / "weekly" / "2026-W39" / "transfermarkt" / "romanian_players.csv").read_text(encoding="utf-8") == "name\nUPDATED\n"
    assert (backup_root / "main" / "transfermarkt" / "romanian_players.csv").read_text(encoding="utf-8") == "name\nUPDATED\n"


def test_run_backup_skips_missing_sources_but_fails_if_none(tmp_path: Path):
    repo = tmp_path / "empty"
    repo.mkdir()
    with pytest.raises(FileNotFoundError):
        run_backup(repo, backup_root=repo / "backups", week_id="2026-W01")


def test_cli_backup_snapshots(tmp_path: Path, monkeypatch, capsys):
    from mws_monitor.cli import main

    repo = tmp_path / "repo"
    repo.mkdir()
    _seed_live(repo)
    monkeypatch.chdir(repo)
    monkeypatch.setattr("sys.argv", ["mws_monitor", "backup-snapshots", "--week", "2026-W40"])
    main()
    assert (repo / "backups" / "weekly" / "2026-W40" / "mws" / "u19" / "latest.md").exists()
    out = capsys.readouterr().out
    assert "2026-W40" in out
