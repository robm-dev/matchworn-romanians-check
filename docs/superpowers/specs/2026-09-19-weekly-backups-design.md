# Weekly backups (main + ISO week folders) — Design

**Date:** 2026-09-19  
**Status:** Approved by user (approach A, Monday 10:00 UTC)  
**Goal:** Keep Transfermarkt player lists and MWS auction outputs in a durable `backups/` tree: a rolling `main/` snapshot plus one folder per ISO week, available both in the GitHub repo and locally after pull.

---

## 1. Problem

Today the repo only keeps “latest” player CSVs under `data/` and “latest” auction reports under `outputs/` (and age-group subdirs). Those files are overwritten by cron jobs, so there is no easy weekly archive of:

- Transfermarkt lists: Romanian, U23, U21, U19  
- MWS auction result sets for the same four tracks  

The user wants **both** a committed repo backup and a local copy (via clone/pull), with weekly folders created on a fixed schedule.

---

## 2. Decisions (locked)

| Decision | Choice |
|---|---|
| Location | Repo path `backups/` **and** local (same tree after `git pull`) |
| Cadence | Once per week — **Monday 10:00 UTC** |
| Layout | Approach **A**: `backups/main/` (overwrite) + `backups/weekly/YYYY-Www/` (historical) |
| Trigger | New GitHub Actions workflow + optional local CLI |
| Existing crons | Unchanged (auctions every ~3 days; player-list refresh monthly) |
| Excel | Out of scope for this design |

---

## 3. Folder layout

```
backups/
  main/
    transfermarkt/
      romanian_players.csv
      top_200_u23_players.csv
      top_200_u21_players.csv
      top_200_u19_players.csv
    mws/
      romanian/
        latest.csv
        latest.json
        latest.md
      u23/
        latest.csv
        latest.json
        latest.md
      u21/
        latest.csv
        latest.json
        latest.md
      u19/
        latest.csv
        latest.json
        latest.md
  weekly/
    2026-W38/          # ISO year-week (UTC week date)
      transfermarkt/   # same files as main
      mws/             # same structure as main
```

### Source → destination mapping

| Source (live) | Backup path under `main/` or `weekly/YYYY-Www/` |
|---|---|
| `data/romanian_players.csv` | `transfermarkt/romanian_players.csv` |
| `data/top_200_u23_players.csv` | `transfermarkt/top_200_u23_players.csv` |
| `data/top_200_u21_players.csv` | `transfermarkt/top_200_u21_players.csv` |
| `data/top_200_u19_players.csv` | `transfermarkt/top_200_u19_players.csv` |
| `outputs/latest.{csv,json,md}` | `mws/romanian/latest.{csv,json,md}` |
| `outputs/u23/latest.{csv,json,md}` | `mws/u23/latest.{csv,json,md}` |
| `outputs/u21/latest.{csv,json,md}` | `mws/u21/latest.{csv,json,md}` |
| `outputs/u19/latest.{csv,json,md}` | `mws/u19/latest.{csv,json,md}` |

### Semantics

- **`main/`:** Always the newest snapshot written by the backup job (full overwrite of those files).  
- **`weekly/YYYY-Www/`:** Snapshot for that ISO week. If the job runs again in the same week (manual re-run), overwrite that week’s folder with a fresh copy from live sources (same as refreshing `main`).  
- Week label uses **UTC** date of the run: Python `datetime.now(timezone.utc).isocalendar()` → `f"{year}-W{week:02d}"`.

Missing source files: skip with a warning (or empty skip list in logs); do not fail the whole job if one age-group output is absent. Fail only if **zero** files were copied.

---

## 4. Automation

### 4.1 GitHub Actions

New workflow: `.github/workflows/backup-weekly.yml`

```yaml
on:
  workflow_dispatch:
  schedule:
    - cron: "0 10 * * 1"   # Monday 10:00 UTC
```

Job outline:

1. Checkout (`fetch-depth: 0`)  
2. Setup Python 3.12 + `pip install -r requirements.txt` (only if CLI lives in the package; a pure-copy step may need no deps beyond stdlib)  
3. Run backup command (see §5)  
4. Upload artifact `mws-weekly-backups` for `backups/**`  
5. Commit & push changed files under `backups/` (same bot identity / rebase-retry pattern as existing auction and player-list workflows)

Permissions: `contents: write`.

**Note:** The weekly job copies **whatever is currently on `main` in the repo** for `data/` and `outputs/` at checkout time. It does **not** re-scrape Transfermarkt or MWS. Freshest lists therefore depend on prior monthly list refresh and ~3-day auction crons. Manual `workflow_dispatch` after a list refresh is supported.

### 4.2 Local

Same CLI:

```bash
python -m mws_monitor backup-snapshots
```

Writes into the repo’s `backups/` tree. User gets GitHub copy via push (Actions) or keeps local-only changes until they pull/push.

---

## 5. Code shape

### Module

Prefer a small dedicated module, e.g. `mws_monitor/backup_snapshots.py`, with:

- `BACKUP_ROOT` default `Path("backups")`  
- `copy_live_to(dest: Path) -> list[Path]` — copy mapped files into `dest/transfermarkt` and `dest/mws/...`  
- `run_backup(backup_root: Path | None = None, week_id: str | None = None) -> dict` — update `main/`, then `weekly/{week_id}/`, return counts/paths  

Use `shutil.copy2` so mtimes are preserved when useful.

### CLI

Register `backup-snapshots` in `mws_monitor/cli.py`:

- `--backup-root` (default `backups`)  
- `--week` optional override (`2026-W38`); default = current UTC ISO week  

### Tests

- Unit test with temp dirs: create fake `data/` + `outputs/` trees, run `run_backup`, assert `main/` and `weekly/YYYY-Www/` contain expected relative paths and file contents.  
- Second run in same week overwrites week folder without creating a duplicate.

---

## 6. Git / repo hygiene

- **Track** `backups/` in git (required for “in repo” + local after pull).  
- Do **not** add `backups/` to `.gitignore`.  
- README: short section documenting layout, Monday 10:00 UTC schedule, and `backup-snapshots` CLI.  
- Large history growth: accept for now (CSVs/JSON/MD are small). Revisit retention (e.g. delete weeks older than N months) only if needed later — **out of scope**.

---

## 7. Non-goals

- Excel / multi-sheet workbooks  
- Changing auction or monthly player-list cron schedules  
- Re-running scrapes inside the weekly backup job  
- Separate absolute path outside the repo for “local only” (local = working copy of `backups/`)

---

## 8. Success criteria

1. After a successful Monday (or manual) run, `backups/main/` matches live `data/` + `outputs/` mappings.  
2. `backups/weekly/{ISO-week}/` exists with the same tree.  
3. Changes are committed on `main` by Actions (when run in CI).  
4. Local `python -m mws_monitor backup-snapshots` produces the same layout.  
5. Existing auction/list workflows remain unchanged.

---

## 9. Open points (none blocking)

None. Retention policy deferred.
