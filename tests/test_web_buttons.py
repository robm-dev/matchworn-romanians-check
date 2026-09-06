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
        "/?view=u23_auctions",
        "/?view=u21_auctions",
        "/?view=u19_auctions",
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


def test_romanian_auction_recheck_runs_checker_and_reports_progress(tmp_path, monkeypatch):
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

    class ImmediateThread:
        def __init__(self, target, daemon):
            self.target = target
            self.daemon = daemon

        def start(self):
            self.target()

    monkeypatch.setattr("mws_monitor.web.ROMANIAN_PLAYERS_PATH", tmp_path / "players.csv")
    monkeypatch.setattr("mws_monitor.web.ROMANIAN_OUTPUT_DIR", tmp_path / "outputs")
    monkeypatch.setattr("mws_monitor.web.run_romanian_auctions", fake_run)
    monkeypatch.setattr("mws_monitor.web.Thread", ImmediateThread)

    client = TestClient(app)
    response = client.post("/romanian-auctions/recheck")

    assert response.status_code == 200
    job_id = response.json()["job_id"]
    status = client.get(f"/romanian-auctions/recheck/status/{job_id}").json()
    assert status["status"] == "complete"
    assert status["percent"] == 100
    assert calls and calls[0][0] == tmp_path / "players.csv"


def test_u23_auction_view_lists_live_auction_links(tmp_path, monkeypatch):
    latest = tmp_path / "latest.json"
    latest.write_text(
        """
{
  "checked_at": "2026-09-06T11:20:47+00:00",
  "match_count": 1,
  "matches": [
    {
      "checked_at": "2026-09-06T11:20:47+00:00",
      "player_name": "Lamine Yamal",
      "transfermarkt_team": "FC Barcelona",
      "position": "Right Winger",
      "market_value_eur": 200000000,
      "mws_name": "Lamine Yamal",
      "event_name": "FC Barcelona - Real Madrid",
      "labels": "Worn, Signed",
      "current_bid_eur": 1200,
      "current_bid_usd": 1400,
      "end_date_utc": "2026-09-14T16:00:00Z",
      "slug": "lamine-live",
      "url": "https://mws.com/us/product/lamine-live"
    }
  ]
}
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr("mws_monitor.web.U23_OUTPUT_PATH", latest)

    response = TestClient(app).get("/?view=u23_auctions")

    assert response.status_code == 200
    assert "Top 200 U23 Auctions" in response.text
    assert "Recheck Top 200 U23" in response.text
    assert "Lamine Yamal" in response.text
    assert "https://mws.com/us/product/lamine-live" in response.text


def test_u21_and_u19_auction_views_list_live_auction_links(tmp_path, monkeypatch):
    latest = tmp_path / "latest.json"
    latest.write_text(
        """
{
  "checked_at": "2026-09-06T11:20:47+00:00",
  "match_count": 1,
  "matches": [
    {
      "checked_at": "2026-09-06T11:20:47+00:00",
      "player_name": "Estevao",
      "transfermarkt_team": "Chelsea FC",
      "position": "Right Winger",
      "market_value_eur": 60000000,
      "mws_name": "Estevao",
      "event_name": "Arsenal - Chelsea",
      "labels": "Issued, Signed",
      "current_bid_eur": 100,
      "current_bid_usd": 117,
      "end_date_utc": "2026-09-13T15:30:00Z",
      "slug": "estevao-live",
      "url": "https://mws.com/us/product/estevao-live"
    }
  ]
}
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr("mws_monitor.web.U21_OUTPUT_PATH", latest)
    monkeypatch.setattr("mws_monitor.web.U19_OUTPUT_PATH", latest)

    client = TestClient(app)

    for view, title, button in [
        ("u21_auctions", "Top 200 U21 Auctions", "Recheck Top 200 U21"),
        ("u19_auctions", "Top 200 U19 Auctions", "Recheck Top 200 U19"),
    ]:
        response = client.get(f"/?view={view}")

        assert response.status_code == 200
        assert title in response.text
        assert button in response.text
        assert "Estevao" in response.text
        assert "https://mws.com/us/product/estevao-live" in response.text


def test_auction_views_render_sortable_column_buttons(tmp_path, monkeypatch):
    latest = tmp_path / "latest.json"
    latest.write_text(
        """
{
  "checked_at": "2026-09-06T11:20:47+00:00",
  "match_count": 0,
  "matches": []
}
""".strip(),
        encoding="utf-8",
    )
    monkeypatch.setattr("mws_monitor.web.ROMANIAN_OUTPUT_PATH", latest)
    monkeypatch.setattr("mws_monitor.web.U23_OUTPUT_PATH", latest)
    monkeypatch.setattr("mws_monitor.web.U21_OUTPUT_PATH", latest)
    monkeypatch.setattr("mws_monitor.web.U19_OUTPUT_PATH", latest)

    client = TestClient(app)

    for path in ["/?view=romanian_auctions", "/?view=u23_auctions", "/?view=u21_auctions", "/?view=u19_auctions"]:
        response = client.get(path)

        assert response.status_code == 200
        assert response.text.count('class="sort-button"') >= 6
        assert 'data-sort-type="number"' in response.text
        assert 'data-sort-type="date"' in response.text


def test_u23_auction_recheck_runs_checker_and_reports_progress(tmp_path, monkeypatch):
    calls = []

    def fake_run(player_list_path, output_dir, settings):
        calls.append((player_list_path, output_dir, settings.mws_web_base_url))
        return []

    class ImmediateThread:
        def __init__(self, target, daemon):
            self.target = target
            self.daemon = daemon

        def start(self):
            self.target()

    monkeypatch.setattr("mws_monitor.web.U23_PLAYERS_PATH", tmp_path / "u23.csv")
    monkeypatch.setattr("mws_monitor.web.U23_OUTPUT_DIR", tmp_path / "u23_outputs")
    monkeypatch.setattr("mws_monitor.web.run_romanian_auctions", fake_run)
    monkeypatch.setattr("mws_monitor.web.Thread", ImmediateThread)

    client = TestClient(app)
    response = client.post("/u23-auctions/recheck")

    assert response.status_code == 200
    job_id = response.json()["job_id"]
    status = client.get(f"/u23-auctions/recheck/status/{job_id}").json()
    assert status["status"] == "complete"
    assert status["percent"] == 100
    assert calls and calls[0][0] == tmp_path / "u23.csv"


def test_u21_and_u19_auction_rechecks_run_checker_and_report_progress(tmp_path, monkeypatch):
    calls = []

    def fake_run(player_list_path, output_dir, settings):
        calls.append((player_list_path, output_dir, settings.mws_web_base_url))
        return []

    class ImmediateThread:
        def __init__(self, target, daemon):
            self.target = target
            self.daemon = daemon

        def start(self):
            self.target()

    monkeypatch.setattr("mws_monitor.web.U21_PLAYERS_PATH", tmp_path / "u21.csv")
    monkeypatch.setattr("mws_monitor.web.U21_OUTPUT_DIR", tmp_path / "u21_outputs")
    monkeypatch.setattr("mws_monitor.web.U19_PLAYERS_PATH", tmp_path / "u19.csv")
    monkeypatch.setattr("mws_monitor.web.U19_OUTPUT_DIR", tmp_path / "u19_outputs")
    monkeypatch.setattr("mws_monitor.web.run_romanian_auctions", fake_run)
    monkeypatch.setattr("mws_monitor.web.Thread", ImmediateThread)

    client = TestClient(app)

    for endpoint in ["/u21-auctions/recheck", "/u19-auctions/recheck"]:
        response = client.post(endpoint)

        assert response.status_code == 200
        job_id = response.json()["job_id"]
        status = client.get(f"{endpoint}/status/{job_id}").json()
        assert status["status"] == "complete"
        assert status["percent"] == 100

    assert calls[0][0] == tmp_path / "u21.csv"
    assert calls[1][0] == tmp_path / "u19.csv"
