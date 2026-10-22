"""Контракт DTO: набор полей, границы валидации, совместимость с портом."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from shared.contracts import (
    BackendPort,
    DeliveryIn,
    DeliveryOut,
    DialogReplyResponse,
    ListingListOut,
    ListingOut,
    NotifySettingsIn,
    PaymentPrepareIn,
    SearchCriteria,
    UserOut,
)
from shared.mocks.backend import MockBackend


def test_dialog_reply_fields_are_frozen() -> None:
    """Ровно этот набор рендерит панель бота — менять нельзя."""
    assert set(DialogReplyResponse.model_fields) == {
        "session_id",
        "text",
        "options",
        "status",
        "finalize_ready",
        "turn_count",
        "criteria",
    }


def test_search_criteria_defaults() -> None:
    criteria = SearchCriteria()
    assert criteria.make is None
    assert criteria.created_from_dialog is False
    # Порядок и состав полей — контракт: сверяем выборочно ключевые.
    for field in ("year_from", "price_max", "mileage_max", "country", "sources"):
        assert field in SearchCriteria.model_fields


def test_delivery_input_bounds() -> None:
    DeliveryIn(price_usd=18000, engine_cc=2000, year=2022)
    with pytest.raises(ValidationError):
        DeliveryIn(price_usd=0, engine_cc=2000, year=2022)
    with pytest.raises(ValidationError):
        DeliveryIn(price_usd=18000, engine_cc=49, year=2022)
    with pytest.raises(ValidationError):
        DeliveryIn(price_usd=18000, engine_cc=2000, year=1900)
    with pytest.raises(ValidationError):
        DeliveryIn(price_usd=18000, engine_cc=2000, year=2022, region="kz")


def test_delivery_output_requires_components_and_totals() -> None:
    fields = set(DeliveryOut.model_fields)
    for name in ("components", "total_rub", "total_usd", "total_local", "age_group"):
        assert name in fields


def test_listing_out_requires_parsed_at() -> None:
    with pytest.raises(ValidationError):
        ListingOut(id=1, source="encar", source_id="x", url="https://e/x")  # без parsed_at


def test_listing_list_out_shape() -> None:
    assert set(ListingListOut.model_fields) == {"total", "items"}


def test_notify_mode_is_literal() -> None:
    NotifySettingsIn(user_id=1, notify_mode="digest")
    with pytest.raises(ValidationError):
        NotifySettingsIn(user_id=1, notify_mode="weekly")


def test_payment_period_bounds() -> None:
    PaymentPrepareIn(user_id=1, tier="pro", period_days=365)
    with pytest.raises(ValidationError):
        PaymentPrepareIn(user_id=1, tier="pro", period_days=0)
    with pytest.raises(ValidationError):
        PaymentPrepareIn(user_id=1, tier="gold", period_days=30)


def test_user_out_roles() -> None:
    fields = set(UserOut.model_fields)
    for name in ("telegram_id", "role", "subscription_tier", "is_active", "onboarded_at"):
        assert name in fields


def test_mock_backend_satisfies_port() -> None:
    assert isinstance(MockBackend(), BackendPort)
