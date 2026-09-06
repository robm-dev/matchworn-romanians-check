from fastapi.testclient import TestClient

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
