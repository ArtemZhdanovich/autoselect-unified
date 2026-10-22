"""Мок-адаптеры: детерминированное поведение домена без инфраструктуры."""

from __future__ import annotations

import asyncio
from typing import Any, Coroutine

import pytest

from shared.contracts.analysis import QuotaExceeded
from shared.mocks.adapters import build_mock_services
from shared.mocks.fixtures import LISTINGS


def run(coro: Coroutine[Any, Any, Any]) -> Any:
    """Синхронная обёртка: pytest-asyncio в зависимостях не нужен."""
    return asyncio.run(coro)


def test_fixtures_are_stable() -> None:
    assert len(LISTINGS) == 12
    assert [item.id for item in LISTINGS] == list(range(1, 13))
    assert LISTINGS[0].make == "Hyundai"


def test_dialog_collects_three_slots() -> None:
    services = build_mock_services()

    async def scenario():
        dialog = services.dialog
        first = await dialog.message(1, "Hyundai Palisade")
        assert first.criteria["make"] == "Hyundai"
        assert first.finalize_ready is False
        assert len(first.options) <= 8

        second = await dialog.message(1, "до 45 000 $")
        assert float(second.criteria["price_max"]) == 45000

        third = await dialog.message(1, "🇰🇷 Корея")
        assert third.finalize_ready is True
        assert third.criteria["country"] == "KR"
        return third

    result = run(scenario())
    assert result.status == "ready"


def test_dialog_restore_and_reset() -> None:
    services = build_mock_services()

    async def scenario():
        await services.dialog.message(7, "Kia Sorento")
        restored = await services.dialog.restore(7)
        assert restored.restored is True
        assert restored.criteria["make"] == "Kia"
        await services.dialog.reset(7)
        return await services.dialog.restore(7)

    assert run(scenario()).restored is False


def test_finalize_reports_sources_and_criteria() -> None:
    services = build_mock_services()
    out = run(services.dialog.finalize(3, {"make": "Kia", "price_max": 40000, "country": "KR"}))
    assert out.sources == ["encar", "kcar"]
    assert out.criteria["make"] == "Kia"


def test_catalog_filters_and_pagination() -> None:
    services = build_mock_services()

    page = run(services.listings.page({}, limit=4, offset=0))
    assert page.total == 12
    assert len(page.items) == 4

    cheap = run(services.listings.page({"price_max": 30000}, limit=10))
    assert cheap.total == 3
    assert all((item.price or 0) <= 30000 for item in cheap.items)

    suv = run(services.listings.page({"body_type": "SUV"}, limit=20))
    assert suv.total == 8


def test_catalog_sort_is_deterministic() -> None:
    """Сортировка по цене — по USD-нормализованной (в каталоге есть KRW-лот)."""
    services = build_mock_services()
    ascending = run(services.listings.page({"sort": "price_asc"}, limit=12))
    normalized = [
        (item.price or 0) / 1350 if (item.currency or "").upper() == "KRW" else (item.price or 0)
        for item in ascending.items
    ]
    assert normalized == sorted(normalized)


def test_get_and_by_url() -> None:
    services = build_mock_services()
    listing = run(services.listings.get(1))
    assert listing is not None and listing.id == 1

    found = run(services.listings.by_url(str(listing.url)))
    assert found is not None and found.id == 1

    assert run(services.listings.by_url("https://unknown.example/x")) is None


def test_analysis_respects_free_quota() -> None:
    services = build_mock_services()
    first = run(services.analysis.analyze(1, 100))
    assert first.verdict in {"deal", "fair", "overpriced"}
    assert first.comps and first.comps["median"] > 0

    with pytest.raises(QuotaExceeded):
        run(services.analysis.analyze(1, 100))

    # другой пользователь — своя квота
    assert run(services.analysis.analyze(1, 101)).price > 0


def test_calc_is_deterministic_and_region_aware() -> None:
    services = build_mock_services()
    first = run(services.calc.delivery(18000, 2000, 2022))
    second = run(services.calc.delivery(18000, 2000, 2022))
    assert first.model_dump() == second.model_dump()
    assert first.total_usd > 18000
    assert first.total_local == first.total_rub
    assert first.currency == "₽"

    belarus = run(services.calc.delivery(18000, 2000, 2022, region="by"))
    assert belarus.currency == "BYN"


def test_compare_sorted_by_total() -> None:
    services = build_mock_services()
    result = run(
        services.calc.compare(
            [
                {"price_usd": 18000, "engine_cc": 2000, "year": 2022},
                {"price_usd": 15000, "engine_cc": 3500, "year": 2019},
            ]
        )
    )
    totals = [row["total_usd"] for row in result.items]
    assert totals == sorted(totals)


def test_billing_payment_is_idempotent() -> None:
    services = build_mock_services()

    async def scenario():
        prepared = await services.billing.prepare(5, "pro", 30)
        assert prepared.amount == 500

        activated = await services.billing.success(prepared.payment_id, 5, "charge-1", 500)
        again = await services.billing.success(prepared.payment_id, 5, "charge-1", 500)
        return activated, again

    activated, again = run(scenario())
    assert activated.tier == "pro"
    assert activated.subscription_until == again.subscription_until  # не продлеваем дважды

    status = run(build_mock_services().billing.status(5))
    assert status.tier == "free"  # состояние не разделяется между контейнерами


def test_notify_counts_saved_searches() -> None:
    services = build_mock_services()

    async def scenario():
        before = await services.notify.settings(9, "digest")
        await services.dialog.finalize(9, {"make": "Kia", "price_max": 30000, "country": "KR"})
        after = await services.notify.settings(9, "digest")
        return before, after

    before, after = run(scenario())
    assert before.updated == 0
    assert after.updated == 1


def test_users_upsert_keeps_identity() -> None:
    services = build_mock_services()

    async def scenario():
        first = await services.users.upsert(42, username="ivan")
        second = await services.users.upsert(42, username="ivan_new")
        return first, second

    first, second = run(scenario())
    assert first.telegram_id == second.telegram_id == 42
    assert second.username == "ivan_new"
    assert second.created_at == first.created_at
