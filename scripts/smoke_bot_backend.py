"""Smoke-проверка связки bot → backend по HTTP, без Telegram.

Зачем: тесты проверяют backend и клиент по отдельности, но не то, что клиент бота
действительно понимает ответы сервиса. Этот скрипт проходит путь старого клиента:
upsert → диалог → финализация → выдача → расчёт → разбор цены.

Запуск (backend уже поднят):
    python scripts/smoke_bot_backend.py http://127.0.0.1:8000
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

# Изолированный Python не кладёт папку скрипта в sys.path — делаем это сами.
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from _bootstrap import prepare_path  # noqa: E402

prepare_path()

from bot_service.port import HttpBackend  # noqa: E402
from shared.contracts.analysis import QuotaExceeded  # noqa: E402
from shared.settings import Settings  # noqa: E402


async def run(base_url: str) -> int:
    settings = Settings.from_env()
    backend = HttpBackend(base_url, settings.internal_token)
    failures: list[str] = []

    def check(name: str, condition: bool, detail: str = "") -> None:
        status = "OK  " if condition else "FAIL"
        print(f"[{status}] {name}{(' — ' + detail) if detail else ''}")
        if not condition:
            failures.append(name)

    try:
        user = await backend.upsert_user(
            telegram_id=555001, username="smoke", first_name="Smoke"
        )
        check("POST /api/users/upsert", user is not None and user.telegram_id == 555001)

        first = await backend.dialog_message(555001, "Hyundai Palisade")
        check(
            "POST /api/dialog/message (ход 1)",
            first is not None and first.criteria.get("make") == "Hyundai",
            f"options={len(first.options) if first else 0}",
        )

        second = await backend.dialog_message(555001, "до 45 000 $")
        check(
            "POST /api/dialog/message (бюджет)",
            second is not None and bool(second.criteria.get("price_max")),
        )

        third = await backend.dialog_message(555001, "🇰🇷 Корея")
        check(
            "POST /api/dialog/message (страна → ready)",
            third is not None and third.finalize_ready,
        )

        finalize = await backend.dialog_finalize(555001)
        check(
            "POST /api/dialog/finalize",
            finalize is not None and finalize.sources == ["encar", "kcar"],
            f"sources={finalize.sources if finalize else None}",
        )

        page = await backend.search_listings_page({"make": "Hyundai"}, limit=5)
        check(
            "GET /api/listings (фильтр по марке)",
            page is not None and page.total >= 1 and len(page.items) <= 5,
            f"total={page.total if page else 'n/a'}",
        )

        listing = await backend.get_listing(1)
        check("GET /api/listings/{id}", listing is not None and listing.id == 1)

        calc = await backend.calc_delivery(18000, 2000, 2022)
        check(
            "POST /api/calc/delivery",
            calc is not None and calc.total_usd > calc.price_usd,
            f"итого ~{calc.total_usd:,.0f} $".replace(",", " ") if calc else "",
        )

        try:
            analysis = await backend.analyze_price(1, 555001)
            check("POST /api/bot/listings/{id}/analysis", analysis is not None)
        except QuotaExceeded:
            check("POST /api/bot/listings/{id}/analysis", True, "квота исчерпана (ожидаемо при повторе)")

        status = await backend.subscription_status(555001)
        check("GET /api/users/{id}/subscription", status is not None)
    finally:
        await backend.aclose()

    print()
    if failures:
        print(f"ПРОВАЛЕНО: {len(failures)} — {', '.join(failures)}")
        return 1
    print("Все проверки пройдены.")
    return 0


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8000"
    raise SystemExit(asyncio.run(run(target)))
