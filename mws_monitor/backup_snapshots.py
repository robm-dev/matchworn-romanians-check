from __future__ import annotations

import shutil
import warnings
from datetime import datetime, timezone
from pathlib import Path

# (relative source under repo_root, relative dest under snapshot root)
SOURCE_MAP: list[tuple[str, str]] = [
    ("data/romanian_players.csv", "transfermarkt/romanian_players.csv"),
    ("data/top_200_u23_players.csv", "transfermarkt/top_200_u23_players.csv"),
    ("data/top_200_u21_players.csv", "transfermarkt/top_200_u21_players.csv"),
    ("data/top_200_u19_players.csv", "transfermarkt/top_200_u19_players.csv"),
    ("outputs/latest.csv", "mws/romanian/latest.csv"),
    ("outputs/latest.json", "mws/romanian/latest.json"),
    ("outputs/latest.md", "mws/romanian/latest.md"),
    ("outputs/u23/latest.csv", "mws/u23/latest.csv"),
    ("outputs/u23/latest.json", "mws/u23/latest.json"),
    ("outputs/u23/latest.md", "mws/u23/latest.md"),
    ("outputs/u21/latest.csv", "mws/u21/latest.csv"),
    ("outputs/u21/latest.json", "mws/u21/latest.json"),
    ("outputs/u21/latest.md", "mws/u21/latest.md"),
    ("outputs/u19/latest.csv", "mws/u19/latest.csv"),
    ("outputs/u19/latest.json", "mws/u19/latest.json"),
    ("outputs/u19/latest.md", "mws/u19/latest.md"),
]


def current_week_id(now: datetime | None = None) -> str:
    moment = now or datetime.now(timezone.utc)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    else:
        moment = moment.astimezone(timezone.utc)
    year, week, _ = moment.isocalendar()
    return f"{year}-W{week:02d}"


def copy_live_to(repo_root: Path, dest: Path) -> tuple[list[Path], list[str]]:
    copied: list[Path] = []
    skipped: list[str] = []
    for src_rel, dest_rel in SOURCE_MAP:
        src = repo_root / src_rel
        target = dest / dest_rel
        if not src.is_file():
            skipped.append(src_rel)
            warnings.warn(f"backup skip missing source: {src_rel}", stacklevel=2)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target)
        copied.append(target)
    return copied, skipped


def run_backup(
    repo_root: Path,
    backup_root: Path | None = None,
    week_id: str | None = None,
) -> dict:
    root = Path(repo_root)
    backups = Path(backup_root) if backup_root is not None else root / "backups"
    week = week_id or current_week_id()

    main_dest = backups / "main"
    week_dest = backups / "weekly" / week

    main_copied, skipped = copy_live_to(root, main_dest)
    if not main_copied:
        raise FileNotFoundError(f"No backup sources found under {root}")
    week_copied, week_skipped = copy_live_to(root, week_dest)
    all_skipped = sorted(set(skipped) | set(week_skipped))

    return {
        "week_id": week,
        "main_copied": main_copied,
        "week_copied": week_copied,
        "skipped": all_skipped,
    }
