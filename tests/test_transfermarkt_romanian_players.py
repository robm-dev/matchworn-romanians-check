from __future__ import annotations

from pathlib import Path

from mws_monitor.transfermarkt_romanian_players import (
    discover_source_bases,
    parse_transfermarkt_players,
    update_romanian_player_csv,
)


def test_parse_transfermarkt_players_extracts_portable_csv_rows():
    html = """
    <table class="items">
      <tbody>
        <tr class="odd">
          <td class="zentriert">1</td>
          <td><a href="/andrei-ratiu/profil/spieler/527966">Andrei Rațiu</a> Right-Back</td>
          <td></td>
          <td class="hauptlink"><a href="/andrei-ratiu/profil/spieler/527966">Andrei Rațiu</a></td>
          <td>Right-Back</td>
          <td class="zentriert">28</td>
          <td class="zentriert"></td>
          <td><a href="/rayo-vallecano/startseite/verein/367"></a> Rayo Vallecano LaLiga</td>
          <td></td>
          <td class="hauptlink"><a href="/rayo-vallecano/startseite/verein/367">Rayo Vallecano</a></td>
          <td><a href="/laliga/startseite/wettbewerb/ES1">LaLiga</a></td>
          <td class="zentriert">30/06/2030</td>
          <td class="rechts hauptlink">€18.00m</td>
        </tr>
        <tr><td></td><td><a href="/andrei-ratiu/profil/spieler/527966">Andrei Rațiu</a></td></tr>
      </tbody>
    </table>
    """

    rows = parse_transfermarkt_players(html, "https://www.transfermarkt.com/source", "Spania")

    assert rows == [
        {
            "Nume": "Andrei Rațiu",
            "Echipă": "Rayo Vallecano",
            "Post": "Right-Back",
            "M.V. (EUR)": "18000000",
            "Vârstă": "28",
            "Țara campionatului": "Spania",
            "Competiție": "LaLiga",
            "Profil Transfermarkt": "https://www.transfermarkt.com/andrei-ratiu/profil/spieler/527966",
            "Lista sursă": "https://www.transfermarkt.com/source",
        }
    ]


def test_discover_source_bases_keeps_country_labels(tmp_path: Path):
    csv_path = tmp_path / "romanian_players.csv"
    csv_path.write_text(
        "\n".join(
            [
                "Nume,Echipă,Post,M.V. (EUR),Vârstă,Țara campionatului,Competiție,Profil Transfermarkt,Lista sursă",
                "A,Team,Post,1,20,Germania,Liga,url,https://www.transfermarkt.com/spieler-statistik/legionaere/statistik/stat/land_id/140/land/40/page/3",
                "B,Team,Post,1,20,Germania,Liga,url,https://www.transfermarkt.com/spieler-statistik/legionaere/statistik/stat/land_id/140/land/40",
            ]
        ),
        encoding="utf-8",
    )

    assert discover_source_bases(csv_path) == [
        ("https://www.transfermarkt.com/spieler-statistik/legionaere/statistik/stat/land_id/140/land/40", "Germania")
    ]


def test_update_romanian_player_csv_paginates_and_writes_rows(tmp_path: Path):
    source_csv = tmp_path / "source.csv"
    output_csv = tmp_path / "updated.csv"
    base = "https://www.transfermarkt.com/spieler-statistik/legionaere/statistik/stat/land_id/140/land/40"
    source_csv.write_text(
        "\n".join(
            [
                "Nume,Echipă,Post,M.V. (EUR),Vârstă,Țara campionatului,Competiție,Profil Transfermarkt,Lista sursă",
                f"Existing,Team,Post,1,20,Germania,Liga,url,{base}",
            ]
        ),
        encoding="utf-8",
    )
    first_page = _html_for("Player One", "/player-one/profil/spieler/1", "Club One", "Bundesliga", "€1.50m")
    second_page = _html_for("Player Two", "/player-two/profil/spieler/2", "Club Two", "2. Bundesliga", "€750k")
    calls = []

    def fetch(url):
        calls.append(url)
        if len(calls) == 1:
            return first_page
        if len(calls) == 2:
            return second_page
        return "<table class=\"items\"><tbody></tbody></table>"

    count = update_romanian_player_csv(source_csv, output_csv, fetch_html=fetch, page_size=1)

    text = output_csv.read_text(encoding="utf-8")
    assert count == 2
    assert "Player One" in text
    assert "Player Two" in text
    assert calls == [base, f"{base}/page/2", f"{base}/page/3"]


def _html_for(name: str, profile_path: str, club: str, league: str, value: str) -> str:
    return f"""
    <table class="items">
      <tbody>
        <tr class="odd">
          <td class="zentriert">1</td>
          <td><a href="{profile_path}">{name}</a> Centre-Back</td>
          <td></td>
          <td class="hauptlink"><a href="{profile_path}">{name}</a></td>
          <td>Centre-Back</td>
          <td class="zentriert">24</td>
          <td class="zentriert"></td>
          <td></td>
          <td></td>
          <td class="hauptlink"><a href="/club/startseite/verein/1">{club}</a></td>
          <td><a href="/league/startseite/wettbewerb/L1">{league}</a></td>
          <td class="zentriert">30/06/2030</td>
          <td class="rechts hauptlink">{value}</td>
        </tr>
      </tbody>
    </table>
    """
