# Auction Market Value Column Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Show Transfermarkt market value on each of the four auction table views (Romanian / U23 / U21 / U19) in the web UI, and mirror it in `latest.md`.

**Architecture:** `market_value_eur` is already present on `AuctionMatch` and in `latest.csv` / `latest.json`. No pipeline or API changes are required. Add one display column in `index.html` for all four views, update `_markdown()` so cron `latest.md` matches, and extend existing web/markdown tests.

**Tech Stack:** Jinja2 templates, FastAPI `TestClient`, pytest, existing `AuctionMatch` dataclass.

## Global Constraints

- Do not change CSV/JSON schema (already includes `market_value_eur`).
- Format market value like the rest of the app: `€{{ "{:,.0f}".format(auction.market_value_eur or 0) }}`.
- When value is missing/`None`/`0`, still show `€0` (same pattern as dashboard `index.html` player tables) — do not invent a new null display.
- Insert the column as **Market value**, immediately after **Player**, before **Item**.
- After inserting the column, re-number all `data-sort-column` indices in that table so sort still works (Player=0, Market value=1, Item=2, Event=3, Bid=4, Ends=5, Action=6).
- Empty-state `colspan` must become `7` (was `6`).
- Keep scope to display only; no Excel weekly archive in this plan.

## File map

| File | Role |
|---|---|
| `mws_monitor/templates/index.html` | Four auction table sections: add header + cell + fix sort indices + colspan |
| `mws_monitor/romanian_auctions.py` | `_markdown()` header/rows for `latest.md` |
| `tests/test_web_buttons.py` | Assert market value appears on Romanian (and one age-group) view |
| `tests/test_romanian_auctions.py` | Assert `latest.md` includes Market value header and formatted value |

---

### Task 1: Failing web test for Market value column

**Files:**
- Modify: `tests/test_web_buttons.py`
- Test: `tests/test_web_buttons.py`

**Interfaces:**
- Consumes: existing fixture pattern in `test_romanian_auction_view_lists_live_auction_links` (`latest.json` with `market_value_eur: 25000000`)
- Produces: assertions that HTML contains `Market value` header and `€25,000,000`

- [ ] **Step 1: Extend the Romanian auction view test**

In `test_romanian_auction_view_lists_live_auction_links`, after the existing asserts, add:

```python
    assert "Market value" in response.text
    assert "€25,000,000" in response.text
```

- [ ] **Step 2: Add a U23 view assertion (same pattern)**

If a U23-specific list test already exists in this file, add the same two asserts there. If not, add a focused test:

```python
def test_u23_auction_view_shows_market_value(tmp_path, monkeypatch):
    latest = tmp_path / "latest.json"
    latest.write_text(
        """
{
  "checked_at": "2026-09-06T11:20:47+00:00",
  "match_count": 1,
  "matches": [
    {
      "checked_at": "2026-09-06T11:20:47+00:00",
      "player_name": "Test U23",
      "transfermarkt_team": "Club",
      "position": "Forward",
      "market_value_eur": 12000000,
      "mws_name": "Test U23",
      "event_name": "Event A - Event B",
      "labels": "Worn",
      "current_bid_eur": 50,
      "current_bid_usd": 55,
      "end_date_utc": "2026-09-14T16:00:00Z",
      "slug": "test-u23",
      "url": "https://mws.com/us/product/test-u23"
    }
  ]
}
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr("mws_monitor.web.U23_OUTPUT_PATH", latest)

    response = TestClient(app).get("/?view=u23_auctions")

    assert response.status_code == 200
    assert "Market value" in response.text
    assert "€12,000,000" in response.text
```

Confirm the monkeypatch attribute name matches `mws_monitor/web.py` (search for `U23_OUTPUT` / `u23` path constants before writing the test; use the exact constant name already used for U23).

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_web_buttons.py::test_romanian_auction_view_lists_live_auction_links tests/test_web_buttons.py::test_u23_auction_view_shows_market_value -v`

Expected: FAIL because HTML has no `Market value` / formatted euro string yet (or U23 path constant mismatch — fix constant name first if Import/AttributeError).

- [ ] **Step 4: Commit**

```bash
git add tests/test_web_buttons.py
git commit -m "test: expect market value on auction table views"
```

---

### Task 2: Add Market value column to all four auction tables in the UI

**Files:**
- Modify: `mws_monitor/templates/index.html` (sections `view == "romanian_auctions"`, `"u23_auctions"`, `"u21_auctions"`, `"u19_auctions"`)

**Interfaces:**
- Consumes: `auction.market_value_eur` from loaded `latest.json` reports
- Produces: sortable Market value column on each of the four pages

- [ ] **Step 1: Update each of the four auction `<thead>` blocks**

Replace the current 6-column header with:

```html
            <th><button class="sort-button" type="button" data-sort-column="0" data-sort-type="text">Player <span aria-hidden="true"></span></button></th>
            <th><button class="sort-button" type="button" data-sort-column="1" data-sort-type="number">Market value <span aria-hidden="true"></span></button></th>
            <th><button class="sort-button" type="button" data-sort-column="2" data-sort-type="text">Item <span aria-hidden="true"></span></button></th>
            <th><button class="sort-button" type="button" data-sort-column="3" data-sort-type="text">Event <span aria-hidden="true"></span></button></th>
            <th><button class="sort-button" type="button" data-sort-column="4" data-sort-type="number">Bid <span aria-hidden="true"></span></button></th>
            <th><button class="sort-button" type="button" data-sort-column="5" data-sort-type="date">Ends <span aria-hidden="true"></span></button></th>
            <th><button class="sort-button" type="button" data-sort-column="6" data-sort-type="text">Action <span aria-hidden="true"></span></button></th>
```

Apply identically in Romanian, U23, U21, and U19 sections.

- [ ] **Step 2: Insert the cell after the Player `<td>` in each of the four row loops**

```html
            <td>€{{ "{:,.0f}".format(auction.market_value_eur or 0) }}</td>
```

Place it immediately after the Player cell (the `<td>` that contains `player_name` / `transfermarkt_team`), before the Item cell.

- [ ] **Step 3: Update empty-state rowspan colspan**

In each of the four `{% else %}` empty rows, change:

```html
<tr><td colspan="6">...</td></tr>
```

to:

```html
<tr><td colspan="7">...</td></tr>
```

Keep the existing empty-state message text unchanged.

- [ ] **Step 4: Run the web tests**

Run: `pytest tests/test_web_buttons.py::test_romanian_auction_view_lists_live_auction_links tests/test_web_buttons.py::test_u23_auction_view_shows_market_value -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add mws_monitor/templates/index.html
git commit -m "feat: show market value on Romanian/U23/U21/U19 auction tables"
```

---

### Task 3: Mirror Market value in `latest.md` and cover with a unit test

**Files:**
- Modify: `mws_monitor/romanian_auctions.py` (`_markdown`)
- Modify: `tests/test_romanian_auctions.py`

**Interfaces:**
- Consumes: `AuctionMatch.market_value_eur`
- Produces: markdown tables with `| Market value |` column for all four cron output dirs (shared writer)

- [ ] **Step 1: Write failing markdown assertion**

In `tests/test_romanian_auctions.py`, in the test that already writes `latest.md` (the one asserting `"Radu Drăgușin" in ... latest.md`), add:

```python
    md = (tmp_path / "latest.md").read_text(encoding="utf-8")
    assert "| Market value |" in md or "| Player | Market value |" in md
    assert "16000000" in md or "16,000,000" in md
```

Use whatever market value the existing test player fixture already sets (today: `16000000` for Drăgușin in that file — match the fixture, do not invent a new number). Prefer displaying a plain integer in markdown (no euro symbol required) for stable asserts, e.g. `16000000`, OR formatted `16,000,000` — pick one format in Step 2 and assert that exact form.

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_romanian_auctions.py -k markdown -v`  
(or the specific test name that covers `write_outputs` / `latest.md`)

Expected: FAIL on Market value header/value.

- [ ] **Step 3: Update `_markdown` in `mws_monitor/romanian_auctions.py`**

Replace header/separator/rows with:

```python
def _markdown(matches: list[AuctionMatch], checked_at_iso: str) -> str:
    lines = [
        "# Romanian MWS Auction Matches",
        "",
        f"Checked at: {checked_at_iso}",
        "",
        "| Player | Market value | Item | Event | Bid EUR | Bid USD | Ends UTC |",
        "|---|---:|---|---|---:|---:|---|",
    ]
    for match in matches:
        market = match.market_value_eur if match.market_value_eur is not None else ""
        lines.append(
            f"| {match.player_name} | {market} | [{match.labels or 'Auction'}]({match.url}) | {match.event_name} | "
            f"{match.current_bid_eur or ''} | {match.current_bid_usd or ''} | {match.end_date_utc} |"
        )
    if not matches:
        lines.append("| No matches |  |  |  |  |  |  |")
    lines.append("")
    return "\n".join(lines)
```

- [ ] **Step 4: Run markdown + web tests**

Run: `pytest tests/test_romanian_auctions.py tests/test_web_buttons.py -v`

Expected: PASS for market-value-related asserts; no unrelated failures introduced.

- [ ] **Step 5: Commit**

```bash
git add mws_monitor/romanian_auctions.py tests/test_romanian_auctions.py
git commit -m "feat: include market value in auction latest.md tables"
```

---

### Task 4: Manual smoke check (optional but recommended)

**Files:** none (runtime)

- [ ] **Step 1: Start the web app locally** (use the project’s existing run command from README, typically `python -m mws_monitor` / uvicorn entry if documented).

- [ ] **Step 2: Open each view and confirm the column**

- `/?view=romanian_auctions`
- `/?view=u23_auctions`
- `/?view=u21_auctions`
- `/?view=u19_auctions`

Confirm: **Market value** header visible, values look like `€25,000,000`, column sorts as a number, empty states still span full width.

- [ ] **Step 3: No commit unless smoke check forced a fix**

If a fix was needed, commit with a short message describing the fix.

---

## Spec coverage self-check

| Requirement | Task |
|---|---|
| Column on Romanian table page | Task 2 |
| Column on U23 / U21 / U19 table pages | Task 2 (same template edits ×4) |
| Data already available — no new scrape | Architecture / no task needed |
| Tests | Tasks 1 and 3 |
| Cron markdown summaries stay consistent | Task 3 |

## Out of scope (explicit)

- Weekly Excel archive / sheet-per-week (separate feature from earlier chat)
- Changing `latest.csv` / `latest.json` fields
- Regenerating committed `outputs/**/latest.*` in this change set (next cron/recheck will refresh `latest.md`)
