# Weekly Backups Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Copy live Transfermarkt player lists and MWS auction outputs into `backups/main/` (overwrite) and `backups/weekly/YYYY-Www/` (one folder per ISO week; older weeks kept), via CLI and a Monday 10:00 UTC GitHub Action.

**Architecture:** A pure-stdlib copy module maps known source paths into a fixed tree under `backups/`. `run_backup()` writes `main/` then the current (or overridden) ISO week folder. CLI wraps it; a new workflow commits `backups/` on schedule. No scrape inside this job.

**Tech Stack:** Python 3.12 stdlib (`shutil`, `pathlib`, `datetime`), argparse CLI, pytest, GitHub Actions `workflow_dispatch` + cron.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-09-19-weekly-backups-design.md`
- Cron: Monday **10:00 UTC** → `0 10 * * 1`
- Layout: `backups/main/{transfermarkt,mws}` + `backups/weekly/YYYY-Www/` (same tree)
- Week id: UTC `isocalendar()` → `f"{year}-W{week:02d}"` (e.g. `2026-W38`)
- Older week folders are **never deleted**; same-week re-run may overwrite that week only
- Missing source files: skip + warn; fail only if zero files copied
- Do not change auction (~3 day) or monthly player-list workflows
- No Excel; no scrape in backup job
- Track `backups/` in git (do not gitignore)

## File map

| File | Responsibility |
|---|---|
| `mws_monitor/backup_snapshots.py` | Mapping, copy helpers, `run_backup`, `current_week_id` |
| `mws_monitor/cli.py` | `backup-snapshots` subcommand |
| `tests/test_backup_snapshots.py` | Unit tests for copy + week folders |
| `.github/workflows/backup-weekly.yml` | Monday 10:00 UTC + manual dispatch |
| `README.md` | Document schedule + CLI + folder layout |

---

### Task 1: Core backup module + failing tests first

**Files:**
- Create: `tests/test_backup_snapshots.py`
- Create: `mws_monitor/backup_snapshots.py`

**Interfaces:**
- Produces:
  - `SOURCE_MAP: list[tuple[Path, Path]]` — relative source → relative dest under a snapshot root
  - `current_week_id(now: datetime | None = None) -> str`
  - `copy_live_to(repo_root: Path, dest: Path) -> list[Path]` — returns copied dest paths
  - `run_backup(repo_root: Path, backup_root: Path | None = None, week_id: str | None = None) -> dict` with keys `week_id`, `main_copied`, `week_copied`, `skipped`

- [ ] **Step 1: Write failing tests**

Create `tests/test_backup_snapshots.py`:

```python
from datetime import datetime, timezone
from pathlib import Path

import pytest

from mws_monitor.backup_snapshots import copy_live_to, current_week_id, run_backup


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
    now = datetime(2026, 9, 19, 12, 0, tzinfo=timezone.utc)  # Saturday ISO week 38
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
    assert len(result_w38["main_copied"]) == 16  # 4 TM + 12 MWS files

    (repo / "data" / "romanian_players.csv").write_text("name\nUPDATED\n", encoding="utf-8")
    result_w39 = run_backup(repo, backup_root=backup_root, week_id="2026-W39")
    assert (backup_root / "weekly" / "2026-W38" / "transfermarkt" / "romanian_players.csv").read_text(encoding="utf-8") == "name\nA\n"
    assert (backup_root / "weekly" / "2026-W39" / "transfermarkt" / "romanian_players.csv").read_text(encoding="utf-8") == "name\nUPDATED\n"
    assert (backup_root / "main" / "transfermarkt" / "romanian_players.csv").read_text(encoding="utf-8") == "name\nUPDATED\n"


def test_run_backup_skips_missing_sources_but_fails_if_none(tmp_path: Path):
    repo = tmp_path / "empty"
    repo.mkdir()
    with pytest.raises(FileNotFoundError):
        run_backup(repo, backup_root=repo / "backups", week_id="2026-W01")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_backup_snapshots.py -v`

Expected: FAIL with `ModuleNotFoundError` or import error for `mws_monitor.backup_snapshots`.

- [ ] **Step 3: Implement `mws_monitor/backup_snapshots.py`**

```python
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
    # Prefer union of skip reasons from first pass; second pass should match
    all_skipped = sorted(set(skipped) | set(week_skipped))

    return {
        "week_id": week,
        "main_copied": main_copied,
        "week_copied": week_copied,
        "skipped": all_skipped,
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_backup_snapshots.py -v`

Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add mws_monitor/backup_snapshots.py tests/test_backup_snapshots.py
git commit -m "feat: add weekly backup snapshot copy module"
```

---

### Task 2: CLI `backup-snapshots`

**Files:**
- Modify: `mws_monitor/cli.py`
- Modify: `tests/test_backup_snapshots.py` (optional CLI smoke) OR rely on module tests — add a thin CLI test if the project has CLI tests; otherwise print-only handler is enough if module is covered.

**Interfaces:**
- Consumes: `run_backup` from Task 1
- Produces: subcommand `python -m mws_monitor backup-snapshots [--backup-root PATH] [--week YYYY-Www] [--repo-root PATH]`

- [ ] **Step 1: Add handler and parser in `cli.py`**

Near other imports:

```python
from .backup_snapshots import run_backup
```

Add command function:

```python
def cmd_backup_snapshots(args: argparse.Namespace) -> None:
    result = run_backup(
        repo_root=Path(args.repo_root),
        backup_root=Path(args.backup_root) if args.backup_root else None,
        week_id=args.week,
    )
    print(
        f"Backup week {result['week_id']}: "
        f"{len(result['main_copied'])} files to main, "
        f"{len(result['week_copied'])} files to weekly/{result['week_id']}."
    )
    if result["skipped"]:
        print(f"Skipped missing: {', '.join(result['skipped'])}")
```

In `build_parser` / `main` subparsers section (after auction parsers is fine):

```python
    backup = sub.add_parser(
        "backup-snapshots",
        help="Copy Transfermarkt lists + MWS outputs into backups/main and backups/weekly/YYYY-Www",
    )
    backup.add_argument("--repo-root", default=".", help="Repository root containing data/ and outputs/")
    backup.add_argument("--backup-root", default=None, help="Override backups directory (default: <repo>/backups)")
    backup.add_argument("--week", default=None, help="ISO week id like 2026-W38 (default: current UTC week)")
    backup.set_defaults(func=cmd_backup_snapshots)
```

- [ ] **Step 2: Smoke-run CLI against a temp tree** (or extend unit test)

Prefer extending `tests/test_backup_snapshots.py`:

```python
def test_cli_backup_snapshots(tmp_path: Path, monkeypatch, capsys):
    from mws_monitor.cli import main

    repo = tmp_path / "repo"
    repo.mkdir()
    _seed_live(repo)
    monkeypatch.chdir(repo)
    main(["backup-snapshots", "--week", "2026-W40"])
    assert (repo / "backups" / "weekly" / "2026-W40" / "mws" / "u19" / "latest.md").exists()
    out = capsys.readouterr().out
    assert "2026-W40" in out
```

Confirm `main` accepts `argv` list — if `main()` only reads `sys.argv`, check existing pattern:

```python
def main(argv: list[str] | None = None) -> None:
    ...
    args = parser.parse_args(argv)
```

If current `main()` has no `argv` param, use:

```python
monkeypatch.setattr("sys.argv", ["mws_monitor", "backup-snapshots", "--week", "2026-W40"])
from mws_monitor.cli import main
main()
```

Inspect `cli.py` `def main` before writing the test and match the existing style.

- [ ] **Step 3: Run tests**

Run: `pytest tests/test_backup_snapshots.py -v`

Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add mws_monitor/cli.py tests/test_backup_snapshots.py
git commit -m "feat: add backup-snapshots CLI command"
```

---

### Task 3: GitHub Actions weekly workflow

**Files:**
- Create: `.github/workflows/backup-weekly.yml`

**Interfaces:**
- Consumes: CLI from Task 2
- Produces: scheduled + manual runs that commit `backups/`

- [ ] **Step 1: Create workflow file**

```yaml
name: Weekly backups

on:
  workflow_dispatch:
  schedule:
    - cron: "0 10 * * 1"

permissions:
  contents: write

jobs:
  backup:
    runs-on: ubuntu-latest

    steps:
      - name: Check out repository
        uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install dependencies
        run: python -m pip install --upgrade pip && pip install -r requirements.txt

      - name: Write main + weekly snapshot
        run: python -m mws_monitor backup-snapshots

      - name: Upload backups artifact
        uses: actions/upload-artifact@v4
        with:
          name: mws-weekly-backups
          path: backups/**

      - name: Commit backups
        run: |
          set -euo pipefail
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add backups/
          if git diff --cached --quiet; then
            echo "No backup changes to commit."
            exit 0
          fi
          git commit -m "Update weekly backups"
          for attempt in 1 2 3 4 5; do
            git pull --rebase origin "${GITHUB_REF_NAME}"
            if git push origin "HEAD:${GITHUB_REF_NAME}"; then
              exit 0
            fi
            echo "Push failed (attempt ${attempt}); retrying..."
            sleep $((attempt * 5))
          done
          echo "Failed to push after retries."
          exit 1
```

- [ ] **Step 2: Validate YAML locally (optional)**

Run: `python -c "import yaml; yaml.safe_load(open('.github/workflows/backup-weekly.yml'))"`  
If PyYAML missing, skip — Actions will validate on push.

- [ ] **Step 3: Commit**

```bash
git add .github/workflows/backup-weekly.yml
git commit -m "ci: add Monday 10:00 UTC weekly backups workflow"
```

---

### Task 4: README + seed first local snapshot (optional verify)

**Files:**
- Modify: `README.md` (GitHub Actions / Outputs sections)

- [ ] **Step 1: Document in README**

Under `## GitHub Actions`, add:

```markdown
### Weekly backups

Every Monday at 10:00 UTC (`0 10 * * 1`), and on manual dispatch:

- Copies Transfermarkt lists (`data/*.csv`) and MWS outputs (`outputs/**/latest.*`) into:
  - `backups/main/` (always overwritten with the latest copy)
  - `backups/weekly/YYYY-Www/` (one folder per ISO week; prior weeks are kept)
- Local equivalent: `python -m mws_monitor backup-snapshots`
```

Under `## Outputs`, add a short bullet for `backups/`.

- [ ] **Step 2: Run one local backup in the real repo** (does not commit outputs unless asked)

Run: `python -m mws_monitor backup-snapshots`

Expected: creates `backups/main/...` and `backups/weekly/<current-week>/...` with 16 files when all sources exist.

- [ ] **Step 3: Commit README (and `backups/` only if user wants the first snapshot in git)**

Default for this task: commit README only.

```bash
git add README.md
git commit -m "docs: document weekly backups layout and schedule"
```

If the user wants the first snapshot committed too:

```bash
git add backups/ README.md
git commit -m "docs: document weekly backups and seed main/week snapshot"
```

---

### Task 5: Trigger workflow once (optional smoke)

- [ ] **Step 1:** After code is on `main`:  
  `gh workflow run "Weekly backups"`  
  Then open the run URL and confirm commit `Update weekly backups` appears if files changed.

- [ ] **Step 2:** No code commit.

---

## Spec coverage self-check

| Spec requirement | Task |
|---|---|
| `backups/main` + `weekly/YYYY-Www` | Task 1 |
| Transfermarkt 4 CSVs + MWS 4 tracks | Task 1 SOURCE_MAP |
| Older weeks kept; same-week overwrite OK | Task 1 test `test_run_backup_writes_main_and_week_without_deleting_prior_week` |
| Monday 10:00 UTC | Task 3 cron |
| CLI local | Task 2 |
| Repo + local via git | Tasks 3–4 |
| No change to other crons | Task 3 new file only |
| Skip missing / fail if zero | Task 1 |
| README | Task 4 |

## Out of scope

- Excel sheets  
- Retention / deleting old weeks  
- Re-scraping inside backup job  
