# MatchWornShirt Romanian Auctions Check

Portable checker for Romanian football players on active MatchWornShirt auctions.

The build compares `data/romanian_players.csv` with all current, not-ended MatchWornShirt bidding products. It keeps football shirts only, normalizes names so diacritics do not break matches, and writes the latest bid information to `outputs/latest.csv`, `outputs/latest.json`, and `outputs/latest.md`.

## Run Locally

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m mws_monitor romanian-auctions
```

Use another player list if needed:

```bash
python -m mws_monitor romanian-auctions \
  --players path/to/players.csv \
  --output-dir outputs
```

CSV input should include at least `Nume`. The bundled file also includes team, position, market value, competition, and Transfermarkt source URL.

## Outputs

- `outputs/latest.csv`: spreadsheet-friendly results
- `outputs/latest.json`: structured results
- `outputs/latest.md`: quick human-readable summary

Each row includes the player, Transfermarkt team, market value, MWS item labels, current EUR/USD bid, closing time, and product URL.

## GitHub Actions

`.github/workflows/mws-romanian-auctions.yml` runs automatically once every 3 days:

```yaml
schedule:
  - cron: "17 7 */3 * *"
```

You can also run it manually from **Actions -> MatchWornShirt Romanian auctions -> Run workflow**.

The workflow:

1. Installs Python dependencies.
2. Runs `python -m mws_monitor romanian-auctions`.
3. Uploads `outputs/latest.*` as an artifact.
4. Commits changed `outputs/latest.*` back to the repository.

## Port To Another Machine

```bash
git clone https://github.com/robm-dev/matchworn-romanians-check.git
cd matchworn-romanians-check
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m mws_monitor romanian-auctions
```

No API key is required. The checker uses MatchWornShirt public catalog endpoints with the public MWS platform key stored in `config/config.yaml`.
