"""Детерминированные фикстуры каталога.

Никакой случайности: тесты и демо должны получать одинаковые id, цены и тексты
при каждом запуске. 12 объявлений хватает, чтобы проверить пагинацию по 4
(как в `deutsche_motors_bot`), «мало результатов» (≤5) и «много» (>5).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any, Final

from shared.contracts.listing import ListingOut

NOW: Final[datetime] = datetime(2026, 10, 20, 9, 0, tzinfo=UTC)
_IMG = "https://cdn.autoselect.example/{name}/{index}.jpg"


def _images(name: str, count: int) -> list[str]:
    return [_IMG.format(name=name, index=i) for i in range(1, count + 1)]


_RAW: Final[tuple[dict[str, Any], ...]] = (
    {
        "id": 1, "source": "encar", "source_id": "EN-100001", "make": "Hyundai", "model": "Palisade",
        "year": 2023, "price": 52000.0, "currency": "USD", "mileage_km": 28000, "vin": "KMH8P8AB1NU100001",
        "body_type": "SUV", "fuel": "diesel", "transmission": "automatic", "drive": "4WD",
        "engine_volume": 2.2, "color": "black", "images": 3,
    },
    {
        "id": 2, "source": "kcar", "source_id": "KC-100002", "make": "Kia", "model": "Sorento",
        "year": 2022, "price": 38500.0, "currency": "USD", "mileage_km": 41000, "vin": "KNAJC81BDN100002",
        "body_type": "SUV", "fuel": "diesel", "transmission": "automatic", "drive": "4WD",
        "engine_volume": 2.2, "color": "white", "images": 2,
    },
    {
        "id": 3, "source": "encar", "source_id": "EN-100003", "make": "Genesis", "model": "GV80",
        "year": 2023, "price": 86400000.0, "currency": "KRW", "mileage_km": 19000, "vin": "KMTGB4SD1PU100003",
        "body_type": "SUV", "fuel": "petrol", "transmission": "automatic", "drive": "4WD",
        "engine_volume": 3.5, "color": "grey", "images": 4,
    },
    {
        "id": 4, "source": "encar", "source_id": "EN-100004", "make": "Hyundai", "model": "Santa Fe",
        "year": 2022, "price": 34900.0, "currency": "USD", "mileage_km": 52000, "vin": "KMHSS81CDNU100004",
        "body_type": "SUV", "fuel": "diesel", "transmission": "automatic", "drive": "2WD",
        "engine_volume": 2.2, "color": "blue", "images": 2,
    },
    {
        "id": 5, "source": "kcar", "source_id": "KC-100005", "make": "Kia", "model": "Carnival",
        "year": 2023, "price": 41000.0, "currency": "USD", "mileage_km": 33000, "vin": "KNANC81BDNU100005",
        "body_type": "minivan", "fuel": "diesel", "transmission": "automatic", "drive": "2WD",
        "engine_volume": 2.2, "color": "white", "images": 3,
    },
    {
        "id": 6, "source": "encar", "source_id": "EN-100006", "make": "BMW", "model": "X5",
        "year": 2021, "price": 58000.0, "currency": "USD", "mileage_km": 61000, "vin": "WBAKS410XMU100006",
        "body_type": "SUV", "fuel": "diesel", "transmission": "automatic", "drive": "4WD",
        "engine_volume": 3.0, "color": "black", "images": 3,
    },
    {
        "id": 7, "source": "encar", "source_id": "EN-100007", "make": "Mercedes-Benz", "model": "GLE",
        "year": 2022, "price": 72500.0, "currency": "USD", "mileage_km": 44000, "vin": "WDC1671201A100007",
        "body_type": "SUV", "fuel": "diesel", "transmission": "automatic", "drive": "4WD",
        "engine_volume": 2.9, "color": "silver", "images": 4,
    },
    {
        "id": 8, "source": "kcar", "source_id": "KC-100008", "make": "Kia", "model": "Sportage",
        "year": 2023, "price": 29900.0, "currency": "USD", "mileage_km": 21000, "vin": "KNAPM81BDNU100008",
        "body_type": "SUV", "fuel": "petrol", "transmission": "automatic", "drive": "2WD",
        "engine_volume": 1.6, "color": "red", "images": 2,
    },
    {
        "id": 9, "source": "encar", "source_id": "EN-100009", "make": "Hyundai", "model": "Tucson",
        "year": 2022, "price": 27500.0, "currency": "USD", "mileage_km": 48000, "vin": "KMHJ381ADNU100009",
        "body_type": "SUV", "fuel": "petrol", "transmission": "automatic", "drive": "2WD",
        "engine_volume": 1.6, "color": "grey", "images": 2,
    },
    {
        "id": 10, "source": "kcar", "source_id": "KC-100010", "make": "Genesis", "model": "G80",
        "year": 2021, "price": 43500.0, "currency": "USD", "mileage_km": 56000, "vin": "KMTG141ABMU100010",
        "body_type": "sedan", "fuel": "petrol", "transmission": "automatic", "drive": "4WD",
        "engine_volume": 2.5, "color": "black", "images": 3,
    },
    {
        "id": 11, "source": "encar", "source_id": "EN-100011", "make": "Hyundai", "model": "Grandeur",
        "year": 2023, "price": 33500.0, "currency": "USD", "mileage_km": 25000, "vin": "KMHL341ABNU100011",
        "body_type": "sedan", "fuel": "petrol", "transmission": "automatic", "drive": "2WD",
        "engine_volume": 2.5, "color": "white", "images": 2,
    },
    {
        "id": 12, "source": "kcar", "source_id": "KC-100012", "make": "Kia", "model": "K5",
        "year": 2022, "price": 24900.0, "currency": "USD", "mileage_km": 39000, "vin": "KNAG341ABNU100012",
        "body_type": "sedan", "fuel": "petrol", "transmission": "automatic", "drive": "2WD",
        "engine_volume": 2.0, "color": "blue", "images": 1,
    },
)


def _build(raw: dict[str, Any]) -> ListingOut:
    index = int(raw["id"])
    return ListingOut(
        id=index,
        source=raw["source"],
        source_id=raw["source_id"],
        url=f"https://www.{raw['source']}.example/cars/{raw['source_id']}",
        make=raw["make"],
        model=raw["model"],
        year=raw["year"],
        price=raw["price"],
        currency=raw["currency"],
        mileage_km=raw["mileage_km"],
        vin=raw["vin"],
        body_type=raw["body_type"],
        fuel=raw["fuel"],
        transmission=raw["transmission"],
        drive=raw["drive"],
        engine_volume=raw["engine_volume"],
        color=raw["color"],
        images=_images(raw["source"], raw["images"]),
        parsed_at=NOW - timedelta(hours=index),
        is_active=True,
        first_seen_at=NOW - timedelta(days=index),
        first_price=float(raw["price"]),
        title_raw=f"{raw['make']} {raw['model']} {raw['year']}",
        title_ru=f"{raw['make']} {raw['model']}, {raw['year']}",
        source_language="kor_Hang",
    )


#: Каталог фикстур в порядке «сначала новые» (как сортировка `new`).
LISTINGS: Final[tuple[ListingOut, ...]] = tuple(_build(item) for item in _RAW)

#: Быстрый доступ по id.
BY_ID: Final[dict[int, ListingOut]] = {item.id: item for item in LISTINGS}

#: Индекс по URL — для «скинь ссылку, покажу карточку».
BY_URL: Final[dict[str, ListingOut]] = {str(item.url): item for item in LISTINGS}

#: Значения списков для селектов админки (Этап 4) — заодно проверка «фильтры работают».
MAKES: Final[tuple[str, ...]] = tuple(dict.fromkeys(item.make or "" for item in LISTINGS))
