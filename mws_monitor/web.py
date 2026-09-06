from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .config import ROOT, load_settings
from .db import SessionLocal, init_db
from .importer import import_watchlist
from .models import Alert, MwsProduct, Player, PlayerAlias, ReviewQueue
from .service import MonitorService, export_results


init_db()
app = FastAPI(title="MWS Value Monitor")
templates = Jinja2Templates(directory=str(ROOT / "mws_monitor" / "templates"))
app.mount("/static", StaticFiles(directory=str(ROOT / "mws_monitor" / "static")), name="static")


def get_session():
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def aware_dt(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request, session: Session = Depends(get_session)):
    min_score = int(request.query_params.get("min_score", 40))
    view = request.query_params.get("view", "live_bargains")
    now = datetime.now(timezone.utc)
    rows = session.execute(
        select(Player, MwsProduct)
        .join(MwsProduct, MwsProduct.player_id == Player.id)
        .order_by(MwsProduct.bargain_score.desc(), MwsProduct.latest_price_eur.asc())
    ).all()
    if view == "live":
        products = [(player, product) for player, product in rows if product.status == "live" and product.bargain_score >= min_score]
    elif view == "closing":
        products = [
            (player, product)
            for player, product in rows
            if product.status == "live" and aware_dt(product.end_date) and now <= aware_dt(product.end_date) <= now + timedelta(hours=24)
        ]
    elif view == "new":
        products = sorted(rows, key=lambda row: row[1].fetched_at, reverse=True)[:100]
    elif view == "finished":
        products = [
            (player, product)
            for player, product in rows
            if product.status == "finished" and product.bargain_score >= min_score
        ]
    else:
        products = [(player, product) for player, product in rows if product.bargain_score >= min_score]
    products = products[:100]
    review = session.scalars(select(ReviewQueue).where(ReviewQueue.status == "open").order_by(ReviewQueue.created_at.desc())).all()
    alerts = session.scalars(select(Alert).order_by(Alert.created_at.desc()).limit(20)).all()
    players = session.scalars(select(Player).order_by(Player.market_value_eur.desc()).limit(200)).all()
    aliases = session.scalars(select(PlayerAlias).order_by(PlayerAlias.input_name.asc())).all()
    alias_player = request.query_params.get("alias_player", "")
    alias_athlete = request.query_params.get("alias_athlete", "")
    alias_category = request.query_params.get("alias_category", "")
    counts = {
        "players": session.scalar(select(func.count()).select_from(Player)) or 0,
        "products": session.scalar(select(func.count()).select_from(MwsProduct)) or 0,
        "live": session.scalar(select(func.count()).select_from(MwsProduct).where(MwsProduct.status == "live")) or 0,
        "review": len(review),
    }
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "products": products,
            "review": review,
            "alerts": alerts,
            "counts": counts,
            "min_score": min_score,
            "view": view,
            "players": players,
            "aliases": aliases,
            "alias_player": alias_player,
            "alias_athlete": alias_athlete,
            "alias_category": alias_category,
        },
    )


@app.get("/import-path")
def import_from_path(path: str, name: str = "watchlist", session: Session = Depends(get_session)):
    import_watchlist(session, Path(path), name)
    session.commit()
    return RedirectResponse("/", status_code=303)


@app.post("/crawl")
def crawl(session: Session = Depends(get_session)):
    settings = load_settings()
    service = MonitorService(session, settings)
    try:
        service.crawl_all()
        session.commit()
    finally:
        service.close()
    return RedirectResponse("/", status_code=303)


@app.get("/crawl")
def crawl_get_hint():
    return RedirectResponse("/", status_code=303)


@app.get("/export")
def export_current_results(session: Session = Depends(get_session)):
    path = ROOT / "exports" / "dashboard_results.csv"
    export_results(session, path)
    return FileResponse(path, media_type="text/csv", filename="mws_value_monitor_results.csv")


@app.get("/product/{product_id}", response_class=HTMLResponse)
def product_detail(product_id: int, request: Request, session: Session = Depends(get_session)):
    row = session.execute(
        select(Player, MwsProduct).join(MwsProduct, MwsProduct.player_id == Player.id).where(MwsProduct.id == product_id)
    ).first()
    if not row:
        return templates.TemplateResponse("not_found.html", {"request": request, "message": "Product not found"}, status_code=404)
    player, product = row
    related_products = session.scalars(
        select(MwsProduct).where(MwsProduct.player_id == player.id).order_by(MwsProduct.end_date.desc().nullslast()).limit(25)
    ).all()
    return templates.TemplateResponse(
        "product.html",
        {"request": request, "player": player, "product": product, "related_products": related_products},
    )


@app.get("/product/{product_id}/ignore")
def ignore_product(product_id: int, session: Session = Depends(get_session)):
    product = session.get(MwsProduct, product_id)
    if product:
        product.bargain_score = 0
        product.bargain_reason = "ignored by user"
        session.commit()
    return RedirectResponse("/", status_code=303)


@app.get("/product/{product_id}/alias")
def alias_from_product(product_id: int, session: Session = Depends(get_session)):
    row = session.execute(
        select(Player, MwsProduct).join(MwsProduct, MwsProduct.player_id == Player.id).where(MwsProduct.id == product_id)
    ).first()
    if not row:
        return RedirectResponse("/?view=aliases", status_code=303)
    player, product = row
    query = (
        f"/?view=aliases&alias_player={player.input_name}"
        f"&alias_athlete={product.mws_athlete_name or ''}"
    )
    return RedirectResponse(query, status_code=303)


@app.get("/alias-save")
def save_alias(
    input_name: str,
    preferred_mws_athlete_name: str = "",
    preferred_mws_category_id: str = "",
    notes: str = "",
    session: Session = Depends(get_session),
):
    alias = session.scalar(select(PlayerAlias).where(PlayerAlias.input_name == input_name))
    if not alias:
        alias = PlayerAlias(input_name=input_name)
        session.add(alias)
    alias.preferred_mws_athlete_name = preferred_mws_athlete_name or None
    alias.preferred_mws_category_id = preferred_mws_category_id or None
    alias.notes = notes or None
    session.commit()
    return RedirectResponse("/?view=aliases", status_code=303)


@app.post("/review/{review_id}/close")
def close_review(review_id: int, session: Session = Depends(get_session)):
    item = session.get(ReviewQueue, review_id)
    if item:
        item.status = "closed"
        session.commit()
    return RedirectResponse("/?view=review", status_code=303)
