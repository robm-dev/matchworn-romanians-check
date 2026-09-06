from __future__ import annotations

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base
from .utils import utcnow


class Watchlist(Base):
    __tablename__ = "watchlists"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    source_path: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utcnow)


class Player(Base):
    __tablename__ = "players"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    input_name: Mapped[str] = mapped_column(String(200), index=True)
    normalized_name: Mapped[str] = mapped_column(String(200), unique=True, index=True)
    team: Mapped[str | None] = mapped_column(String(200))
    age: Mapped[int | None] = mapped_column(Integer)
    position: Mapped[str | None] = mapped_column(String(100))
    market_value_eur: Mapped[int] = mapped_column(Integer, default=0)
    categories: Mapped[str] = mapped_column(String(500), default="")
    best_rank: Mapped[int | None] = mapped_column(Integer)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    products = relationship("MwsProduct", back_populates="player")


class PlayerAlias(Base):
    __tablename__ = "player_aliases"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    input_name: Mapped[str] = mapped_column(String(200), unique=True)
    preferred_mws_athlete_name: Mapped[str | None] = mapped_column(String(200))
    preferred_mws_category_id: Mapped[str | None] = mapped_column(String(80))
    notes: Mapped[str | None] = mapped_column(Text)


class MwsAthlete(Base):
    __tablename__ = "mws_athletes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mws_category_id: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(200), index=True)
    confidence: Mapped[float] = mapped_column(Float, default=0)
    match_note: Mapped[str | None] = mapped_column(Text)
    player_id: Mapped[int | None] = mapped_column(ForeignKey("players.id"))


class MwsProduct(Base):
    __tablename__ = "mws_products"
    __table_args__ = (UniqueConstraint("mws_product_id", name="uq_mws_product_id"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    mws_product_id: Mapped[str] = mapped_column(String(80), index=True)
    slug: Mapped[str] = mapped_column(String(300), index=True)
    url: Mapped[str] = mapped_column(String(600))
    player_id: Mapped[int] = mapped_column(ForeignKey("players.id"), index=True)
    mws_athlete_name: Mapped[str | None] = mapped_column(String(200))
    shirt_team: Mapped[str | None] = mapped_column(String(200))
    event_name: Mapped[str | None] = mapped_column(String(300))
    labels: Mapped[str | None] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(40), index=True)
    sales_method: Mapped[str | None] = mapped_column(String(80))
    start_date: Mapped[object | None] = mapped_column(DateTime(timezone=True))
    end_date: Mapped[object | None] = mapped_column(DateTime(timezone=True), index=True)
    latest_price_eur: Mapped[int | None] = mapped_column(Integer)
    final_price_eur: Mapped[int | None] = mapped_column(Integer)
    bargain_score: Mapped[int] = mapped_column(Integer, default=0, index=True)
    bargain_reason: Mapped[str | None] = mapped_column(Text)
    fetched_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utcnow)

    player = relationship("Player", back_populates="products")
    snapshots = relationship("PriceSnapshot", back_populates="product")


class PriceSnapshot(Base):
    __tablename__ = "price_snapshots"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int] = mapped_column(ForeignKey("mws_products.id"), index=True)
    price_eur: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(40))
    fetched_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utcnow)

    product = relationship("MwsProduct", back_populates="snapshots")


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    product_id: Mapped[int | None] = mapped_column(ForeignKey("mws_products.id"))
    level: Mapped[str] = mapped_column(String(40), default="info")
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utcnow)
    sent_at: Mapped[object | None] = mapped_column(DateTime(timezone=True))


class ReviewQueue(Base):
    __tablename__ = "review_queue"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    player_id: Mapped[int | None] = mapped_column(ForeignKey("players.id"))
    input_name: Mapped[str] = mapped_column(String(200), index=True)
    reason: Mapped[str] = mapped_column(Text)
    candidates_json: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(40), default="open", index=True)
    created_at: Mapped[object] = mapped_column(DateTime(timezone=True), default=utcnow)
