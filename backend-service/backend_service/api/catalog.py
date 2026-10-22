"""Каталог и AI-разбор цены: `/api/listings*`, `/api/bot/listings/{id}/analysis`."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query, status

from backend_service.api.deps import ContainerDep, require_internal
from shared.contracts.analysis import AnalysisOut, BotAnalysisRequest
from shared.contracts.listing import ListingListOut, ListingOut

router = APIRouter(prefix="/api/listings", tags=["catalog"])

bot_router = APIRouter(
    prefix="/api/bot/listings",
    tags=["analysis"],
    dependencies=[Depends(require_internal)],
)


@router.get("", response_model=ListingListOut)
async def list_listings(
    container: ContainerDep,
    make: str | None = None,
    model: str | None = None,
    year_from: int | None = Query(default=None, ge=1900),
    year_to: int | None = Query(default=None, ge=1900),
    price_min: float | None = Query(default=None, ge=0),
    price_max: float | None = Query(default=None, ge=0),
    currency: str | None = None,
    mileage_min: int | None = Query(default=None, ge=0),
    mileage_max: int | None = Query(default=None, ge=0),
    body_type: str | None = None,
    fuel: str | None = None,
    transmission: str | None = None,
    drive: str | None = None,
    engine_volume_min: float | None = Query(default=None, ge=0, le=20),
    engine_volume_max: float | None = Query(default=None, ge=0, le=20),
    color: str | None = None,
    source: str | None = None,
    sort: str = Query(default="new", pattern="^(new|price_asc|price_desc|mileage_asc|year_desc)$"),
    limit: int = Query(default=20, ge=1, le=50),
    offset: int = Query(default=0, ge=0),
) -> ListingListOut:
    """Лента с фильтрами и сортировкой. Набор параметров — часть контракта."""
    params = {
        "make": make,
        "model": model,
        "year_from": year_from,
        "year_to": year_to,
        "price_min": price_min,
        "price_max": price_max,
        "currency": currency,
        "mileage_min": mileage_min,
        "mileage_max": mileage_max,
        "body_type": body_type,
        "fuel": fuel,
        "transmission": transmission,
        "drive": drive,
        "engine_volume_min": engine_volume_min,
        "engine_volume_max": engine_volume_max,
        "color": color,
        "source": source,
        "sort": sort,
    }
    return await container.catalog.page(params, limit=limit, offset=offset)


@router.get("/facets")
async def listing_facets(container: ContainerDep) -> dict:
    """Агрегаты для фильтров Mini App.

    Этап 2: считаются по текущей выдаче каталога (в real-режиме — из legacy).
    """
    page = await container.catalog.page({}, limit=50, offset=0)
    makes: dict[str, int] = {}
    for item in page.items:
        if item.make:
            makes[item.make] = makes.get(item.make, 0) + 1
    return {"total": page.total, "makes": makes}


@router.get("/by-url", response_model=ListingOut)
async def get_listing_by_url(url: str, container: ContainerDep) -> ListingOut:
    """«Скинь ссылку — покажу карточку»: поиск объявления по URL источника."""
    listing = await container.catalog.by_url(url)
    if listing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")
    return listing


@router.get("/{listing_id}", response_model=ListingOut)
async def get_listing(listing_id: int, container: ContainerDep) -> ListingOut:
    listing = await container.catalog.get(listing_id)
    if listing is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Listing not found")
    return listing


@bot_router.post("/{listing_id}/analysis", response_model=AnalysisOut)
async def bot_create_analysis(
    listing_id: int, body: BotAnalysisRequest, container: ContainerDep
) -> AnalysisOut:
    """AI-разбор цены для бота.

    403 = квота Free исчерпана (бот показывает апселл), 503 = LLM/рынок недоступны.
    """
    return await container.analysis.analyze(listing_id, body.user_id)
