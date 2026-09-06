from pathlib import Path

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

from mws_monitor.db import Base
from mws_monitor.importer import import_watchlist
from mws_monitor.models import Player


def test_import_watchlist_dedupes_players(tmp_path: Path):
    csv_path = tmp_path / "players.csv"
    csv_path.write_text(
        "category,rank,name,team,age,position,value\n"
        "u21,1,Lamine Yamal,FC Barcelona,17,Right Winger,€200.00m\n"
        "u23,1,Lamine Yamal,FC Barcelona,17,Right Winger,€200.00m\n",
        encoding="utf-8",
    )
    engine = create_engine("sqlite:///:memory:", future=True)
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine, future=True)
    with Session() as session:
        imported = import_watchlist(session, csv_path, "test")
        session.commit()
        players = session.scalars(select(Player)).all()
    assert imported == 2
    assert len(players) == 1
    assert players[0].categories == "u21,u23"
