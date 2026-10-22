"""AI-анализ стоимости — контракт `POST /api/bot/listings/{id}/analysis` (internal)."""

from __future__ import annotations

from pydantic import BaseModel, Field


class BotAnalysisRequest(BaseModel):
    user_id: int  # telegram_id


class AnalysisOut(BaseModel):
    """Разбор цены: вердикт, рынок, справедливый диапазон, факторы."""

    verdict: str
    price: float
    currency: str
    fair_min: float | None = None
    fair_max: float | None = None
    summary: str | None = None
    factors: list[str] = []
    comps: dict | None = None
    history: list[dict] = []
    source: str = "ai"
    created_at: str | None = None


class QuotaExceeded(Exception):
    """Бесплатная квота разборов исчерпана → бот показывает апселл (HTTP 403)."""


class AnalysisUnavailable(Exception):
    """LLM/рынок недоступны → бот пишет «попробуйте позже» (HTTP 503)."""
