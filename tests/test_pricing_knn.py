from pathlib import Path

import pytest

from mws_monitor.pricing_knn import (
    bid_ladder,
    estimate_fair_knn,
    labels_to_mws_type,
    load_comp_rows_from_workbook,
    load_tm_overrides_csv,
    mws_type_bucket,
    parse_event_player_title,
)
from mws_monitor.utils import normalize_name

ROOT = Path(__file__).resolve().parents[1]
WORKBOOK = ROOT / "player_pricing_model_ranked.xlsx"


def test_mws_type_bucket():
    assert mws_type_bucket("Worn, Signed") == "worn_signed"
    assert mws_type_bucket("Issued") == "issued"
    assert mws_type_bucket("Issued, Signed") == "issued_signed"


def test_bid_ladder_roundtrip():
    assert bid_ladder(1000) == (600, 750, 850)


def test_parse_event_player_title():
    assert parse_event_player_title("Cole Palmer | Chelsea") == ("Cole Palmer", "Chelsea")
    assert parse_event_player_title("Solo") == ("Solo", None)


def test_labels_to_mws_type():
    assert labels_to_mws_type([{"text": "Worn"}, {"text": "Signed"}]) == "Worn, Signed"


@pytest.mark.skipif(not WORKBOOK.exists(), reason="workbook fixture missing")
def test_load_comp_rows():
    rows = load_comp_rows_from_workbook(WORKBOOK)
    assert len(rows) >= 50
    assert all(r.market_value_eur > 0 for r in rows)


@pytest.mark.skipif(not WORKBOOK.exists(), reason="workbook fixture missing")
def test_knn_near_cole_palmer():
    comps = load_comp_rows_from_workbook(WORKBOOK)
    fair, note = estimate_fair_knn(120_000_000, 487, "Issued", comps, k=5)
    assert fair > 0
    assert "kNN" in note
    assert 500 < fair < 4000


def test_tm_overrides_csv(tmp_path):
    p = tmp_path / "tm.csv"
    p.write_text("name,market_value_eur,mws_last_price_eur\nFoo Bar,50000000,100\n", encoding="utf-8")
    by_name, by_slug = load_tm_overrides_csv(p)
    assert by_name[normalize_name("Foo Bar")]["market_value_eur"] == 50_000_000
    assert by_name[normalize_name("Foo Bar")]["mws_last_price_eur"] == 100
    assert by_slug == {}

    p2 = tmp_path / "tm2.csv"
    p2.write_text("name,market_value_eur,mws_slug\n,12000000,abc-product-slug\n", encoding="utf-8")
    _, slug_map = load_tm_overrides_csv(p2)
    assert slug_map["abc-product-slug"]["market_value_eur"] == 12_000_000
