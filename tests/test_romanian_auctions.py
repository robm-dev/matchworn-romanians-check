from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from mws_monitor.romanian_auctions import (
    fetch_live_bidding_products,
    load_romanian_players,
    match_players_to_products,
    write_outputs,
)


def test_load_romanian_players_detects_transfermarkt_header(tmp_path: Path):
    workbook = tmp_path / "players.xlsx"
    raw = pd.DataFrame(
        [
            ["Jucatori romani", None, None, None],
            ["metadata", None, None, None],
            [None, None, None, None],
            ["Nume", "Echipă", "Post", "M.V. (EUR)"],
            ["Radu Drăgușin", "ACF Fiorentina", "Fundaș central", 16000000],
            ["Ioan Vermeșan", "Hellas Verona", "Atacant central", 1000000],
        ]
    )
    raw.to_excel(workbook, sheet_name="Jucători", header=False, index=False)

    players = load_romanian_players(workbook)

    assert [player.name for player in players] == ["Radu Drăgușin", "Ioan Vermeșan"]
    assert players[0].normalized_name == "radu dragusin"
    assert players[0].market_value_eur == 16000000


def test_load_romanian_players_accepts_generic_u23_csv_headers(tmp_path: Path):
    csv_path = tmp_path / "u23.csv"
    csv_path.write_text(
        "\n".join(
            [
                "name,team,position,market_value_eur,age,source_url",
                "Lamine Yamal,FC Barcelona,Right Winger,200000000,17,https://www.transfermarkt.com/lamine-yamal/profil/spieler/937958",
            ]
        ),
        encoding="utf-8",
    )

    players = load_romanian_players(csv_path)

    assert players[0].name == "Lamine Yamal"
    assert players[0].team == "FC Barcelona"
    assert players[0].market_value_eur == 200000000


def test_match_players_to_products_uses_normalized_names_and_live_bidding_shirts():
    players = [
        _player("Radu Drăgușin", "ACF Fiorentina", 16000000),
        _player("Ioan Vermeșan", "Hellas Verona", 1000000),
    ]
    products = [
        _product("Radu Drăgușin", "radu-live", "bidding", "football_shirt"),
        _product("Ioan Vermesan", "ioan-live", "bidding", "football_shirt"),
        _product("Radu Drăgușin", "radu-buy-now", "fixed_price", "football_shirt"),
        _product("Ioan Vermeșan", "ioan-ball", "bidding", "football"),
    ]

    matches = match_players_to_products(players, products)

    assert {match.slug for match in matches} == {"radu-live", "ioan-live"}
    assert next(match for match in matches if match.slug == "ioan-live").player_name == "Ioan Vermeșan"


def test_fetch_live_bidding_products_pages_until_empty():
    calls = []

    class FakeClient:
        def get_json(self, path, params, cache=False):
            calls.append((path, dict(params), cache))
            if params["offset"] == 0:
                return {"total_count": 121, "results": [_product("A", "a", "bidding", "football_shirt")]}
            if params["offset"] == 120:
                return {"total_count": 121, "results": [_product("B", "b", "bidding", "football_shirt")]}
            return {"total_count": 121, "results": []}

    products = fetch_live_bidding_products(FakeClient(), page_size=120)

    assert [product["slug"] for product in products] == ["a", "b"]
    assert [call[1]["offset"] for call in calls] == [0, 120]
    assert calls[0][1]["only_return_not_ended"] is True


def test_write_outputs_creates_csv_json_and_markdown(tmp_path: Path):
    matches = [
        match_players_to_products(
            [_player("Radu Drăgușin", "ACF Fiorentina", 16000000)],
            [_product("Radu Drăgușin", "radu-live", "bidding", "football_shirt")],
        )[0]
    ]

    write_outputs(matches, tmp_path, checked_at_iso="2026-09-06T10:48:46+00:00")

    assert (tmp_path / "latest.csv").read_text(encoding="utf-8").splitlines()[0].startswith("checked_at")
    data = json.loads((tmp_path / "latest.json").read_text(encoding="utf-8"))
    assert data["match_count"] == 1
    assert "Radu Drăgușin" in (tmp_path / "latest.md").read_text(encoding="utf-8")


def _player(name: str, team: str, market_value_eur: int):
    from mws_monitor.romanian_auctions import RomanianPlayer

    return RomanianPlayer(
        name=name,
        normalized_name=name.lower().replace("ă", "a").replace("ș", "s"),
        team=team,
        position="",
        market_value_eur=market_value_eur,
        source_url="",
    )


def _product(name: str, slug: str, sales_method: str, product_type: str):
    return {
        "id": slug,
        "name": name,
        "slug": slug,
        "sales_method": sales_method,
        "type": product_type,
        "finished": False,
        "product_event_name": "ACF Fiorentina - Torino FC",
        "end_date": "2026-09-14T16:00:00Z",
        "prices": [{"currency": "EUR", "price": 121}, {"currency": "USD", "price": 140}],
        "labels": [{"text": "Worn"}, {"text": "Signed"}],
    }
