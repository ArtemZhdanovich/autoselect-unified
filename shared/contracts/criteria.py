"""SearchCriteria — контракт поиска, перенесён из `auto_bot/app/schemas/criteria.py` 1:1.

Любое изменение полей/типов здесь = breaking change для Mini App, бота и партнёров.
`SourceConfig`/`SourceHealth` не переносятся: они нужны только админке (Этап 4).
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import BaseModel


class SearchCriteria(BaseModel):
    # Основное
    make: str | None = None
    model: str | None = None
    generation: str | None = None

    # Годы
    year_from: int | None = None
    year_to: int | None = None

    # Цена
    price_min: Decimal | None = None
    price_max: Decimal | None = None
    currency: str | None = None

    # Пробег
    mileage_max: int | None = None

    # Характеристики
    fuel: str | None = None
    transmission: str | None = None
    drive: str | None = None
    body_type: str | None = None
    color: str | None = None
    engine_volume_min: float | None = None
    engine_volume_max: float | None = None

    # География и источник
    country: str | None = None  # "KR", "DE", "US", "CN", "JP"
    sources: list[str] | None = None  # явный список источников
    location: str | None = None

    # Состояние
    not_damaged: bool | None = None
    no_accidents: bool | None = None
    seller_type: str | None = None

    # Свободные заметки
    notes: str | None = None

    # Метаданные
    created_from_dialog: bool = False
    dialog_session_id: str | None = None
