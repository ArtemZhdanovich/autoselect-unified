"""Калькулятор доставки — контракт `/api/calc/*`, перенесён 1:1 из `auto_bot/app/api/calc.py`."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class DeliveryIn(BaseModel):
    price_usd: float = Field(gt=0, le=1_000_000)
    engine_cc: int = Field(default=2000, ge=50, le=10_000)
    year: int = Field(ge=1980, le=2100)
    power_hp: int | None = Field(default=None, ge=10, le=2000)
    # Юрисдикция расчёта (валюта объявления: BYN → РБ, RUB → РФ)
    region: Literal["ru", "by"] = "ru"


class DeliveryOut(BaseModel):
    price_usd: float
    engine_cc: int
    year: int
    age_years: int
    age_group: str
    region: str = "ru"
    currency: str = "₽"
    power_hp: int | None = None
    util_category: str = "льготный"
    util_note: str = ""
    components: list[dict]
    legal_refs: list[dict] = []
    total_rub: float
    total_usd: float
    total_local: float
    rates_note: str = "Курс фиксированный (MVP). Логистика/брокер/СБКТС — средние по рынку."


class CompareIn(BaseModel):
    """Сравнение нескольких вариантов «под ключ»."""

    items: list[dict] = Field(min_length=1, max_length=10)


class CompareOut(BaseModel):
    items: list[dict] = Field(default_factory=list)
