"""Объявление — контракт выдачи, перенесён из `auto_bot/app/schemas/listing.py` 1:1.

`InspectionReport*` (карта повреждений) не переносится: это исключительно веб-PDP,
бот и Mini App его не читают — см. `docs/STAGE1_ANALYSIS.md` §2.8.
"""

from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


def _utcnow() -> datetime:
    return datetime.now(UTC)


class UnifiedListing(BaseModel):
    """Единый формат объявления на выходе адаптеров-парсеров."""

    # Идентификация
    source: str  # "encar", "kcar", "che168"
    source_id: str  # ID внутри источника
    url: HttpUrl
    schema_version: int = 1

    # Основное
    title: Optional[str] = None
    make: Optional[str] = None
    model: Optional[str] = None
    generation: Optional[str] = None
    year: Optional[int] = None

    # Цена
    price: Optional[Decimal] = None
    currency: Optional[str] = None  # "KRW", "EUR", "USD"

    # Характеристики
    mileage_km: Optional[int] = None
    vin: Optional[str] = None
    body_type: Optional[str] = None
    fuel: Optional[str] = None
    transmission: Optional[str] = None
    drive: Optional[str] = None
    engine_volume: Optional[float] = None
    color: Optional[str] = None

    # Продавец и локация
    location: Optional[str] = None
    seller_type: Optional[Literal["private", "dealer", "auction"]] = None
    condition: Optional[str] = None

    # Медиа
    images: list[HttpUrl] = Field(default_factory=list)

    # Время
    published_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    parsed_at: datetime = Field(default_factory=_utcnow)

    # Сырые данные для отладки и перепарсинга
    raw: dict[str, Any] = Field(default_factory=dict)


class FetchResult(BaseModel):
    items: list[UnifiedListing]
    next_cursor: str | None = None
    has_more: bool = False
    source_meta: dict[str, Any] = Field(default_factory=dict)


class PricePointOut(BaseModel):
    """Точка истории цен."""

    price: float
    currency: Optional[str] = None
    recorded_at: datetime


class ListingOut(BaseModel):
    """Объявление для ленты/карточки (Mini App и бот)."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    source: str
    source_id: str
    url: str
    make: Optional[str] = None
    model: Optional[str] = None
    year: Optional[int] = None
    price: Optional[float] = None
    currency: Optional[str] = None
    mileage_km: Optional[int] = None
    vin: Optional[str] = None
    # Спеки (миграция 0016): кузов/топливо/КПП/привод — фильтры и карточки.
    body_type: Optional[str] = None
    fuel: Optional[str] = None
    transmission: Optional[str] = None
    drive: Optional[str] = None
    # Объём (литры) и цвет — миграция 0017.
    engine_volume: Optional[float] = None
    color: Optional[str] = None
    images: list[Any] = Field(default_factory=list)
    parsed_at: datetime

    # Отслеживание: is_active/first_seen_at приходят из ORM.
    is_active: bool = True
    first_seen_at: Optional[datetime] = None
    first_price: Optional[float] = None
    price_history: Optional[list[PricePointOut]] = None
    updated_at: Optional[datetime] = None
    last_seen_at: Optional[datetime] = None
    price_changed_at: Optional[datetime] = None

    # Перевод тайтла (NLLB): оригинал + перевод + язык оригинала.
    title_raw: Optional[str] = None
    title_ru: Optional[str] = None
    source_language: Optional[str] = None


class ListingListOut(BaseModel):
    total: int
    items: list[ListingOut]
