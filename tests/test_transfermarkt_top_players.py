from __future__ import annotations

from pathlib import Path

from mws_monitor.transfermarkt_top_players import parse_top_players, update_top_players_csv


def test_parse_top_players_extracts_rows_from_transfermarkt_html():
    html = """
    <table class="items">
      <tbody>
        <tr class="odd">
          <td class="zentriert">1</td>
          <td><a href="/lamine-yamal/profil/spieler/937958">Lamine Yamal</a> Right Winger</td>
          <td></td>
          <td class="hauptlink"><a href="/lamine-yamal/profil/spieler/937958">Lamine Yamal</a></td>
          <td>Right Winger</td>
          <td class="zentriert">17</td>
          <td class="zentriert"></td>
          <td class="zentriert"><a href="/fc-barcelona/startseite/verein/131" title="FC Barcelona"></a></td>
          <td class="rechts hauptlink">€200.00m</td>
        </tr>
      </tbody>
    </table>
    """

    rows = parse_top_players(html, "https://www.transfermarkt.com/top?page=1")

    assert rows == [
        {
            "rank": "1",
            "name": "Lamine Yamal",
            "team": "FC Barcelona",
            "position": "Right Winger",
            "market_value_eur": "200000000",
            "age": "17",
            "source_url": "https://www.transfermarkt.com/lamine-yamal/profil/spieler/937958",
            "list_source_url": "https://www.transfermarkt.com/top?page=1",
        }
    ]


def test_update_top_players_csv_paginates_to_limit(tmp_path: Path):
    output = tmp_path / "u23.csv"
    base_url = "https://www.transfermarkt.com/top?page=1"
    calls = []

    def fetch(url):
        calls.append(url)
        return _html_for(str(len(calls)), f"Player {len(calls)}")

    count = update_top_players_csv(base_url, output, fetch_html=fetch, limit=2, page_size=1)

    text = output.read_text(encoding="utf-8")
    assert count == 2
    assert "Player 1" in text
    assert "Player 2" in text
    assert calls == [base_url, "https://www.transfermarkt.com/top?page=2"]


def _html_for(rank: str, name: str) -> str:
    slug = name.lower().replace(" ", "-")
    return f"""
    <table class="items">
      <tbody>
        <tr class="odd">
          <td class="zentriert">{rank}</td>
          <td><a href="/{slug}/profil/spieler/{rank}">{name}</a> Centre-Back</td>
          <td></td>
          <td class="hauptlink"><a href="/{slug}/profil/spieler/{rank}">{name}</a></td>
          <td>Centre-Back</td>
          <td class="zentriert">22</td>
          <td class="zentriert"></td>
          <td class="zentriert"><a href="/club/startseite/verein/1" title="Club {rank}"></a></td>
          <td class="rechts hauptlink">€1.00m</td>
        </tr>
      </tbody>
    </table>
    """
