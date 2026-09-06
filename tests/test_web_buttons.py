from fastapi.testclient import TestClient

from mws_monitor.romanian_auctions import AuctionMatch
from mws_monitor.web import app


def test_dashboard_button_routes_render():
    client = TestClient(app)
    for path in [
        "/",
        "/?view=live",
        "/?view=closing",
        "/?view=new",
        "/?view=finished",
        "/?view=review",
        "/?view=watchlist",
        "/?view=aliases",
        "/?view=romanian_auctions",
        "/export",
        "/crawl",
    ]:
        response = client.get(path, follow_redirects=False)
        assert response.status_code in {200, 303}


def test_alias_save_route():
    client = TestClient(app)
    response = client.get(
        "/alias-save",
        params={
            "input_name": "Test Alias Player",
            "preferred_mws_athlete_name": "Test MWS Athlete",
            "preferred_mws_category_id": "test-category-id",
            "notes": "test note",
        },
        follow_redirects=False,
    )
    assert response.status_code == 303


def test_romanian_auction_view_lists_live_auction_links(tmp_path, monkeypatch):
    latest = tmp_path / "latest.json"
    latest.write_text(
        """
{
  "checked_at": "2026-09-06T11:20:47+00:00",
  "match_count": 1,
  "matches": [
    {
      "checked_at": "2026-09-06T11:20:47+00:00",
      "player_name": "Radu Drăgușin",
      "transfermarkt_team": "Tottenham Hotspur",
      "position": "Centre-Back",
      "market_value_eur": 25000000,
      "mws_name": "Radu Drăgușin",
      "event_name": "ACF Fiorentina - Torino FC",
      "labels": "Worn, Signed",
      "current_bid_eur": 121,
      "current_bid_usd": 140,
      "end_date_utc": "2026-09-14T16:00:00Z",
      "slug": "radu-live",
      "url": "https://mws.com/us/product/radu-live"
    }
  ]
}
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr("mws_monitor.web.ROMANIAN_OUTPUT_PATH", latest)

    response = TestClient(app).get("/?view=romanian_auctions")

    assert response.status_code == 200
    assert "Recheck Romanian Auctions" in response.text
    assert "Radu Drăgușin" in response.text
    assert "https://mws.com/us/product/radu-live" in response.text
    assert "View Auction" in response.text


def test_romanian_auction_recheck_runs_checker_and_redirects(tmp_path, monkeypatch):
    calls = []

    def fake_run(player_list_path, output_dir, settings):
        calls.append((player_list_path, output_dir, settings.mws_web_base_url))
        return [
            AuctionMatch(
                checked_at="2026-09-06T11:20:47+00:00",
                player_name="Ioan Vermeșan",
                transfermarkt_team="Hellas Verona",
                position="Forward",
                market_value_eur=1000000,
                mws_name="Ioan Vermeșan",
                event_name="Calcio Padova - Hellas Verona FC",
                labels="Issued, Signed",
                current_bid_eur=68,
                current_bid_usd=80,
                end_date_utc="2026-09-07T16:00:00Z",
                slug="ioan-live",
                url="https://mws.com/us/product/ioan-live",
            )
        ]

    monkeypatch.setattr("mws_monitor.web.ROMANIAN_PLAYERS_PATH", tmp_path / "players.csv")
    monkeypatch.setattr("mws_monitor.web.ROMANIAN_OUTPUT_DIR", tmp_path / "outputs")
    monkeypatch.setattr("mws_monitor.web.run_romanian_auctions", fake_run)

    response = TestClient(app).post("/romanian-auctions/recheck", follow_redirects=False)

    assert response.status_code == 303
    assert response.headers["location"] == "/?view=romanian_auctions"
    assert calls and calls[0][0] == tmp_path / "players.csv"
