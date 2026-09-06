from mws_monitor.matcher import resolve_match


def test_pedri_manual_alias_wins():
    match = resolve_match(
        "Pedri",
        [{"id": "bad", "name": "Fernando Zampedri"}],
        {"preferred_mws_athlete_name": "Pedri González", "preferred_mws_category_id": "good", "notes": ""},
    )
    assert match.status == "found"
    assert match.category_id == "good"


def test_low_confidence_goes_to_review():
    match = resolve_match("Rayan", [{"id": "x", "name": "Rayan Kolli"}], None)
    assert match.status == "needs_review"


def test_exact_match_found():
    match = resolve_match("Lamine Yamal", [{"id": "x", "name": "Lamine Yamal"}], None)
    assert match.status == "found"
    assert match.confidence == 100
