# MatchWornShirt Tracked Auctions Check

Portable checker for Romanian football players and the Transfermarkt Top 200 U23, U21, and U19 lists on active MatchWornShirt auctions.

The build compares tracked player lists with all current, not-ended MatchWornShirt bidding products. It keeps football shirts only, normalizes names so diacritics do not break matches, and writes the latest bid information to CSV, JSON, and Markdown.

## Run Locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m mws_monitor romanian-auctions
python -m mws_monitor u23-auctions
python -m mws_monitor u21-auctions
python -m mws_monitor u19-auctions
```

Open the local web interface:

```bash
python -m mws_monitor serve --host 127.0.0.1 --port 8765
```

Then visit:

- `http://127.0.0.1:8765/?view=romanian_auctions` and use **Recheck Romanian Auctions**
- `http://127.0.0.1:8765/?view=u23_auctions` and use **Recheck Top 200 U23**
- `http://127.0.0.1:8765/?view=u21_auctions` and use **Recheck Top 200 U21**
- `http://127.0.0.1:8765/?view=u19_auctions` and use **Recheck Top 200 U19**

Use another player list if needed:

```bash
python -m mws_monitor romanian-auctions \
  --players path/to/players.csv \
  --output-dir outputs
```

CSV input should include at least `Nume`. The bundled file also includes team, position, market value, competition, and Transfermarkt source URL.

Refresh the Transfermarkt player lists manually:

```bash
python -m mws_monitor update-romanian-players
python -m mws_monitor update-u23-players
python -m mws_monitor update-u21-players
python -m mws_monitor update-u19-players
```

## Outputs

- `outputs/latest.csv`: Romanian player auction results
- `outputs/latest.json`: Romanian structured results
- `outputs/latest.md`: Romanian quick summary
- `outputs/u23/latest.csv`: Top 200 U23 auction results
- `outputs/u23/latest.json`: Top 200 U23 structured results
- `outputs/u23/latest.md`: Top 200 U23 quick summary
- `outputs/u21/latest.csv`: Top 200 U21 auction results
- `outputs/u21/latest.json`: Top 200 U21 structured results
- `outputs/u21/latest.md`: Top 200 U21 quick summary
- `outputs/u19/latest.csv`: Top 200 U19 auction results
- `outputs/u19/latest.json`: Top 200 U19 structured results
- `outputs/u19/latest.md`: Top 200 U19 quick summary

Each row includes the player, Transfermarkt team, market value, MWS item labels, current EUR/USD bid, closing time, and product URL.

## GitHub Actions

`.github/workflows/mws-romanian-auctions.yml` runs automatically once every 3 days:

```yaml
schedule:
  - cron: "17 7 */3 * *"
  - cron: "27 7 */3 * *"
  - cron: "37 7 */3 * *"
  - cron: "47 7 */3 * *"
```

You can also run it manually from **Actions -> MatchWornShirt tracked auctions -> Run workflow**.

The scheduled workflow runs the four checks 10 minutes apart:

- `07:17 UTC`: Romanian players
- `07:27 UTC`: Top 200 U23
- `07:37 UTC`: Top 200 U21
- `07:47 UTC`: Top 200 U19

Manual runs execute all four checks in one run.

The workflow:

1. Installs Python dependencies.
2. Runs the selected tracked auction checks.
3. Uploads latest outputs as an artifact.
4. Commits changed outputs back to the repository.

`.github/workflows/update-player-lists.yml` runs monthly on the 1st day of the month. It refreshes `data/romanian_players.csv`, `data/top_200_u23_players.csv`, `data/top_200_u21_players.csv`, and `data/top_200_u19_players.csv` from Transfermarkt, reruns all MWS checks, uploads the files, and commits any changes.

## Port To Another Machine

```bash
git clone https://github.com/robm-dev/matchworn-romanians-check.git
cd matchworn-romanians-check
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m mws_monitor romanian-auctions
python -m mws_monitor u23-auctions
python -m mws_monitor u21-auctions
python -m mws_monitor u19-auctions
```

No API key is required. The checker uses MatchWornShirt public catalog endpoints with the public MWS platform key stored in `config/config.yaml`.
