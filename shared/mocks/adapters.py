"""Мок-адаптеры домена: детерминированные реализации портов для `MODE=mock`.

Живут в `shared`, потому что нужны двум потребителям:

* `backend-service` — подставляет их вместо реальных адаптеров (MODE=mock);
* `bot-service` — через `MockBackend` поднимает бота **без бэкенда вообще** (make up-bot).

Все алгоритмы намеренно простые и повторяемые: мок — это эталон поведения,
а не имитация ML. Числа в калькуляторе — заглушка, помеченная в `rates_note`.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from typing import Any, Iterable

from shared.contracts.analysis import AnalysisOut, AnalysisUnavailable, QuotaExceeded
from shared.contracts.delivery import CompareOut, DeliveryOut
from shared.contracts.dialog import (
    DialogFinalizeOut,
    DialogReplyResponse,
    DialogResetOut,
    DialogRestoreOut,
)
from shared.contracts.listing import ListingListOut, ListingOut
from shared.contracts.notifications import NotifySettingsOut
from shared.contracts.payments import (
    PaymentPrepareOut,
    PaymentSuccessOut,
    UserSubscriptionOut,
)
from shared.contracts.users import LoginLinkConfirmOut, UserOut
from shared.mocks import fixtures

NOW = fixtures.NOW


# --------------------------------------------------------------------- состояние


@dataclass
class MemoryState:
    """Общее состояние моков: то, что в реальном сервисе лежит в PostgreSQL."""

    users: dict[int, UserOut] = field(default_factory=dict)
    #: user_id → сколько поисков финализировано (влияет на /resume).
    searches: dict[int, int] = field(default_factory=dict)
    #: user_id → {"notify_mode": str, "quiet_hours": str | None}
    notify: dict[int, dict[str, Any]] = field(default_factory=dict)
    #: payment_id → описание платежа
    payments: dict[int, dict[str, Any]] = field(default_factory=dict)
    #: user_id → {"tier": str, "until": datetime | None}
    subscriptions: dict[int, dict[str, Any]] = field(default_factory=dict)
    #: (user_id, listing_id) → число разборов за неделю
    analyses: dict[tuple[int, int], int] = field(default_factory=dict)
    _payment_seq: int = 0

    def next_payment_id(self) -> int:
        self._payment_seq += 1
        return self._payment_seq


# ----------------------------------------------------------------------- каталог


def _usd_price(item: ListingOut) -> float:
    price = float(item.price or 0)
    if (item.currency or "").upper() == "KRW":
        return price / 1350.0
    return price


def _matches(item: ListingOut, params: dict[str, Any]) -> bool:
    def text_eq(value: str | None, expected: Any) -> bool:
        return not expected or (value or "").lower() == str(expected).lower()

    if not text_eq(item.make, params.get("make")):
        return False
    if params.get("model") and str(params["model"]).lower() not in (item.model or "").lower():
        return False
    if not text_eq(item.source, params.get("source")):
        return False
    if params.get("year_from") is not None and (item.year or 0) < int(params["year_from"]):
        return False
    if params.get("year_to") is not None and (item.year or 0) > int(params["year_to"]):
        return False
    if params.get("price_min") is not None and _usd_price(item) < float(params["price_min"]):
        return False
    if params.get("price_max") is not None and _usd_price(item) > float(params["price_max"]):
        return False
    if params.get("mileage_min") is not None and (item.mileage_km or 0) < int(params["mileage_min"]):
        return False
    if params.get("mileage_max") is not None and (item.mileage_km or 0) > int(params["mileage_max"]):
        return False
    for key in ("body_type", "fuel", "transmission", "drive", "color"):
        expected = params.get(key)
        if expected and str(expected).lower() not in (getattr(item, key) or "").lower():
            return False
    if params.get("engine_volume_min") is not None and (item.engine_volume or 0) < float(
        params["engine_volume_min"]
    ):
        return False
    if params.get("engine_volume_max") is not None and (item.engine_volume or 0) > float(
        params["engine_volume_max"]
    ):
        return False
    return True


def _sort(items: list[ListingOut], sort: str) -> list[ListingOut]:
    if sort == "price_asc":
        return sorted(items, key=lambda i: (_usd_price(i), -i.id))
    if sort == "price_desc":
        return sorted(items, key=lambda i: (-_usd_price(i), -i.id))
    if sort == "mileage_asc":
        return sorted(items, key=lambda i: (i.mileage_km or 10**9, -i.id))
    if sort == "year_desc":
        return sorted(items, key=lambda i: (-(i.year or 0), -i.id))
    return sorted(items, key=lambda i: (-int((i.parsed_at - NOW).total_seconds()), -i.id))


class MockListings:
    """Порт каталога: фильтры, сортировка, пагинация — как у `GET /api/listings`."""

    def __init__(self, items: Iterable[ListingOut] | None = None) -> None:
        self.items: tuple[ListingOut, ...] = tuple(items) if items is not None else fixtures.LISTINGS

    async def page(self, params: dict[str, Any] | None = None, limit: int = 20, offset: int = 0) -> ListingListOut:
        params = {k: v for k, v in (params or {}).items() if v not in (None, "")}
        found = [item for item in self.items if _matches(item, params)]
        found = _sort(found, str(params.get("sort") or "new"))
        total = len(found)
        return ListingListOut(total=total, items=found[offset : offset + limit])

    async def get(self, listing_id: int) -> ListingOut | None:
        return fixtures.BY_ID.get(int(listing_id))

    async def by_url(self, url: str) -> ListingOut | None:
        direct = fixtures.BY_URL.get(url.strip())
        if direct is not None:
            return direct
        # Терпим хвостовой слэш/параметры — как реальный `/api/listings/by-url`.
        normalized = url.strip().rstrip("/").split("?")[0]
        for known, item in fixtures.BY_URL.items():
            if known.rstrip("/") == normalized:
                return item
        return None


# ------------------------------------------------------------------------- диалог

MAKE_OPTIONS: tuple[str, ...] = (
    "Hyundai",
    "Kia",
    "Genesis",
    "BMW",
    "Mercedes-Benz",
    "Toyota",
    "Lexus",
)
BUDGET_OPTIONS: tuple[str, ...] = (
    "до 30 000 $",
    "30 000–45 000 $",
    "45 000–60 000 $",
    "60 000+ $",
)
COUNTRY_OPTIONS: tuple[str, ...] = ("🇰🇷 Корея", "🇨🇳 Китай")

_YEAR_RE = re.compile(r"\b(19\d{2}|20\d{2})\b")
_MONEY_RE = re.compile(r"(\d[\d\s]*)\s*(к|k|тыс)?")


def _parse_free_text(text: str) -> dict[str, Any]:
    """Вытащить из фразы марку, годы и бюджет. Простая эвристика — этого достаточно."""
    criteria: dict[str, Any] = {}
    lowered = text.lower()

    for make in MAKE_OPTIONS:
        if make.lower() in lowered:
            criteria["make"] = make
            break

    years = [int(y) for y in _YEAR_RE.findall(text)]
    if len(years) >= 2:
        criteria["year_from"], criteria["year_to"] = min(years), max(years)
    elif years:
        criteria["year_from"] = years[0]

    prices: list[int] = []
    for raw, suffix in _MONEY_RE.findall(text):
        digits = int(raw.replace(" ", ""))
        if 1900 <= digits <= 2100:  # это год, а не деньги
            continue
        if suffix:
            digits *= 1000
        if 1000 <= digits <= 1_000_000:
            prices.append(digits)
    if len(prices) >= 2:
        criteria["price_min"], criteria["price_max"] = min(prices), max(prices)
    elif prices:
        criteria["price_max"] = prices[0]

    if "дизел" in lowered:
        criteria["fuel"] = "diesel"
    elif "бензин" in lowered:
        criteria["fuel"] = "petrol"
    if "внедорожник" in lowered or "suv" in lowered:
        criteria["body_type"] = "SUV"
    return criteria


def _apply_option(option: str) -> dict[str, Any]:
    """Кнопка-опция → критерий. Ровно те же смыслы, что в промпте агента."""
    if option in MAKE_OPTIONS:
        return {"make": option}
    if option in BUDGET_OPTIONS:
        numbers = [int(n.replace(" ", "")) for n in re.findall(r"\d[\d\s]*", option)]
        numbers = [n for n in numbers if n >= 1000]
        if "+" in option and numbers:
            return {"price_min": numbers[0]}
        if len(numbers) >= 2:
            return {"price_min": numbers[0], "price_max": numbers[1]}
        if numbers:
            return {"price_max": numbers[0]}
        return {}
    if option in COUNTRY_OPTIONS:
        return {"country": "KR" if "Корея" in option else "CN"}
    return {}


@dataclass
class _DialogSession:
    criteria: dict[str, Any] = field(default_factory=dict)
    turn: int = 0
    messages: list[dict[str, str]] = field(default_factory=list)
    options: list[str] = field(default_factory=list)


class MockDialog:
    """Сценарный диалог: собирает критерии по шагам, без LLM.

    Повторяет поведение `auto_bot` на уровне контракта: `options` ≤ 8,
    `finalize_ready` становится True, когда заполнены марка, бюджет и страна.
    """

    def __init__(self, state: MemoryState | None = None) -> None:
        self.state = state or MemoryState()
        self.sessions: dict[int, _DialogSession] = {}

    def _session(self, user_id: int) -> _DialogSession:
        return self.sessions.setdefault(int(user_id), _DialogSession())

    async def message(self, user_id: int, text: str) -> DialogReplyResponse:
        session = self._session(user_id)
        session.turn += 1
        session.messages.append({"role": "user", "content": text})

        applied = _apply_option(text) if text in session.options else _parse_free_text(text)
        session.criteria.update({k: v for k, v in applied.items() if v is not None})

        criteria = session.criteria
        has_car = bool(criteria.get("make") or criteria.get("model"))
        has_price = bool(criteria.get("price_max") or criteria.get("price_min"))
        has_geo = bool(criteria.get("country") or criteria.get("sources"))
        ready = has_car and has_price and has_geo

        if not has_car:
            reply = "Подберу машину. С какой марки начнём?"
            options = list(MAKE_OPTIONS)
        elif not has_price:
            reply = "Отлично. Какой бюджет рассматриваете?"
            options = list(BUDGET_OPTIONS)
        elif not has_geo:
            reply = "Из какой страны везём?"
            options = list(COUNTRY_OPTIONS)
        else:
            reply = "Параметры собраны — можно запускать поиск."
            options = []

        session.options = options[:8]
        session.messages.append({"role": "assistant", "content": reply})

        return DialogReplyResponse(
            session_id=f"mock-{user_id}",
            text=reply,
            options=session.options,
            status="ready" if ready else "collecting",
            finalize_ready=ready,
            turn_count=session.turn,
            criteria=dict(criteria),
        )

    async def reset(self, user_id: int) -> DialogResetOut:
        self.sessions.pop(int(user_id), None)
        return DialogResetOut()

    async def restore(self, user_id: int) -> DialogRestoreOut:
        session = self.sessions.get(int(user_id))
        if session is None or not session.messages:
            return DialogRestoreOut()
        return DialogRestoreOut(
            restored=True,
            messages=session.messages[-6:],
            criteria=dict(session.criteria),
        )

    async def finalize(self, user_id: int, criteria: dict[str, Any] | None = None) -> DialogFinalizeOut:
        session = self._session(user_id)
        if criteria:
            session.criteria.update({k: v for k, v in criteria.items() if v is not None})
        self.state.searches[int(user_id)] = self.state.searches.get(int(user_id), 0) + 1
        return DialogFinalizeOut(
            sources=["encar", "kcar"],
            criteria=dict(session.criteria),
        )


# ------------------------------------------------------------------- AI-разбор


class MockAnalysis:
    """Разбор цены по медиане фикстур. Квота free: 1 разбор на (юзера, машину)."""

    def __init__(self, state: MemoryState | None = None, free_quota: int = 1) -> None:
        self.state = state or MemoryState()
        self.free_quota = free_quota

    async def analyze(self, listing_id: int, user_id: int) -> AnalysisOut:
        key = (int(user_id), int(listing_id))
        used = self.state.analyses.get(key, 0)
        if used >= self.free_quota:
            raise QuotaExceeded("бесплатный разбор этой машины на неделе уже использован")
        listing = fixtures.BY_ID.get(int(listing_id))
        if listing is None:
            raise AnalysisUnavailable(f"объявление {listing_id} не найдено")

        peers = [
            _usd_price(item)
            for item in fixtures.LISTINGS
            if item.make == listing.make and item.id != listing.id
        ]
        peer_prices = peers or [_usd_price(listing)]
        peer_prices.sort()
        median = peer_prices[len(peer_prices) // 2]
        price = _usd_price(listing)

        fair_min, fair_max = round(median * 0.92), round(median * 1.08)
        if price < fair_min:
            verdict = "deal"
        elif price > fair_max:
            verdict = "overpriced"
        else:
            verdict = "fair"

        self.state.analyses[key] = used + 1
        return AnalysisOut(
            verdict=verdict,
            price=price,
            currency="USD",
            fair_min=float(fair_min),
            fair_max=float(fair_max),
            summary="Мок-разбор: медиана по сопоставимым объявлениям фикстур.",
            factors=[
                "пробег в пределах среднего",
                "год выпуска выше среднего по выборке",
                "дизель дороже бензина на вторичке Кореи",
            ],
            comps={"count": len(peer_prices), "median": float(median)},
            history=[],
            source="mock",
        )


# ------------------------------------------------------------------ калькулятор


class MockCalc:
    """Смета «под ключ». Числа — заглушка, помечены в `rates_note`."""

    SHIPPING_USD = 1800.0
    BROKER_USD = 1200.0
    SBKTS_USD = 400.0
    USD_RUB = 92.0
    USD_BYN = 3.2

    def _duty(self, price_usd: float, engine_cc: int, age: int) -> float:
        if age < 3:
            return round(price_usd * 0.15)
        if age <= 5:
            return round(engine_cc * 1.5)
        return round(engine_cc * 3.0)

    def _util(self, engine_cc: int) -> tuple[float, str]:
        if engine_cc <= 2000:
            return 5200.0, "льготный"
        if engine_cc <= 3000:
            return 8900.0, "льготный"
        return 24000.0, "полный"

    def _breakdown(self, price_usd: float, engine_cc: int, year: int, region: str) -> DeliveryOut:
        age = max(0, NOW.year - int(year))
        duty = self._duty(price_usd, engine_cc, age)
        util_usd, util_category = self._util(engine_cc)
        components = [
            {"label": "Авто", "usd": round(price_usd), "rub": round(price_usd * self.USD_RUB)},
            {"label": "Море", "usd": round(self.SHIPPING_USD), "rub": round(self.SHIPPING_USD * self.USD_RUB)},
            {"label": "Брокер", "usd": round(self.BROKER_USD), "rub": round(self.BROKER_USD * self.USD_RUB)},
            {"label": "Пошлина", "usd": round(duty), "rub": round(duty * self.USD_RUB)},
            {"label": "СБКТС/ЭПТС", "usd": round(self.SBKTS_USD), "rub": round(self.SBKTS_USD * self.USD_RUB)},
            {"label": "Утильсбор", "usd": round(util_usd), "rub": round(util_usd * self.USD_RUB)},
        ]
        total_usd = sum(c["usd"] for c in components)
        total_rub = total_usd * self.USD_RUB
        currency = "₽" if region == "ru" else "BYN"
        total_local = total_rub if region == "ru" else round(total_rub / self.USD_RUB * self.USD_BYN)
        age_group = "до 3 лет" if age < 3 else ("3–5 лет" if age <= 5 else "старше 5 лет")
        return DeliveryOut(
            price_usd=round(price_usd),
            engine_cc=int(engine_cc),
            year=int(year),
            age_years=age,
            age_group=age_group,
            region=region,
            currency=currency,
            util_category=util_category,
            util_note="Мок-расчёт: ставки условные, для проверки UI.",
            components=components,
            legal_refs=[],
            total_rub=round(total_rub),
            total_usd=round(total_usd),
            total_local=round(total_local),
        )

    async def delivery(self, price_usd: float, engine_cc: int, year: int, power_hp: int | None = None, region: str = "ru") -> DeliveryOut:
        return self._breakdown(float(price_usd), int(engine_cc), int(year), region)

    async def compare(self, items: list[dict[str, Any]]) -> CompareOut:
        results: list[dict[str, Any]] = []
        for item in items[:10]:
            try:
                breakdown = self._breakdown(
                    float(item["price_usd"]),
                    int(item.get("engine_cc", 2000)),
                    int(item["year"]),
                    str(item.get("region", "ru")),
                )
            except (KeyError, TypeError, ValueError):
                continue
            results.append(
                {
                    "title": item.get("title")
                    or f"{breakdown.year} г. · {breakdown.engine_cc} см³",
                    "price_usd": breakdown.price_usd,
                    "total_usd": breakdown.total_usd,
                    "total_rub": breakdown.total_rub,
                    "total_local": breakdown.total_local,
                    "currency": breakdown.currency,
                    "age_group": breakdown.age_group,
                }
            )
        results.sort(key=lambda row: row["total_usd"])
        return CompareOut(items=results)


# --------------------------------------------------------------------- биллинг

TIER_PRICES: dict[str, dict[int, int]] = {
    "pro": {30: 500, 365: 4800},
    "business": {30: 2500},
}
TIER_TITLES = {"pro": "AutoPick Pro", "business": "AutoPick Business"}
TIER_DESCRIPTIONS = {
    "pro": "20 фильтров, 200 AI-поисков/день, instant-уведомления, price drop",
    "business": "Без лимитов, API, CRM-интеграция, приоритетная поддержка",
}


class MockBilling:
    def __init__(self, state: MemoryState | None = None) -> None:
        self.state = state or MemoryState()

    async def status(self, user_id: int) -> UserSubscriptionOut:
        record = self.state.subscriptions.get(int(user_id), {})
        return UserSubscriptionOut(
            user_id=int(user_id),
            tier=record.get("tier", "free"),
            subscription_until=record.get("until"),
        )

    async def prepare(self, user_id: int, tier: str, period_days: int) -> PaymentPrepareOut:
        prices = TIER_PRICES.get(tier)
        if prices is None:
            raise ValueError(f"неизвестный тариф: {tier}")
        amount = prices.get(int(period_days))
        if amount is None:
            raise ValueError(f"тариф {tier} не продаётся на {period_days} дней")
        payment_id = self.state.next_payment_id()
        self.state.payments[payment_id] = {
            "user_id": int(user_id),
            "tier": tier,
            "period_days": int(period_days),
            "amount": amount,
            "status": "pending",
        }
        period = "год" if int(period_days) >= 365 else "мес"
        return PaymentPrepareOut(
            payment_id=payment_id,
            amount=amount,
            tier=tier,
            period_days=int(period_days),
            title=TIER_TITLES[tier],
            description=f"{TIER_DESCRIPTIONS[tier]} — {amount} Stars/{period}",
        )

    async def success(
        self, payment_id: int, user_id: int, provider_payment_id: str, amount: int
    ) -> PaymentSuccessOut:
        payment = self.state.payments.get(int(payment_id))
        if payment is None or payment["user_id"] != int(user_id):
            raise KeyError("платёж не найден")
        if payment["status"] != "paid":
            payment["status"] = "paid"
            payment["provider_payment_id"] = provider_payment_id
            until = NOW + timedelta(days=int(payment["period_days"]))
            self.state.subscriptions[int(user_id)] = {"tier": payment["tier"], "until": until}
        record = self.state.subscriptions.get(int(user_id), {})
        return PaymentSuccessOut(
            activated=True,
            tier=record.get("tier", payment["tier"]),
            subscription_until=record.get("until"),
        )


# ------------------------------------------------------------------ уведомления


class MockNotify:
    def __init__(self, state: MemoryState | None = None) -> None:
        self.state = state or MemoryState()

    def _updated(self, user_id: int) -> int:
        """Сколько фильтров обновлено: в моке «фильтр» появляется после поиска."""
        return 1 if self.state.searches.get(int(user_id), 0) > 0 else 0

    async def settings(
        self,
        user_id: int,
        notify_mode: str | None = None,
        quiet_hours: str | None = None,
        quiet_hours_clear: bool = False,
    ) -> NotifySettingsOut:
        record = self.state.notify.setdefault(int(user_id), {"notify_mode": "instant", "quiet_hours": None})
        if notify_mode is not None:
            record["notify_mode"] = notify_mode
        if quiet_hours_clear:
            record["quiet_hours"] = None
        elif quiet_hours is not None:
            record["quiet_hours"] = quiet_hours
        return NotifySettingsOut(user_id=int(user_id), updated=self._updated(user_id))


# ------------------------------------------------------------------ пользователи


class MockUsers:
    def __init__(self, state: MemoryState | None = None) -> None:
        self.state = state or MemoryState()

    async def upsert(
        self,
        telegram_id: int,
        username: str | None = None,
        first_name: str | None = None,
        last_name: str | None = None,
        language_code: str | None = None,
    ) -> UserOut:
        existing = self.state.users.get(int(telegram_id))
        user = UserOut(
            telegram_id=int(telegram_id),
            username=username,
            first_name=first_name,
            last_name=last_name,
            language_code=language_code,
            role=existing.role if existing else "buyer",
            subscription_tier=existing.subscription_tier if existing else "free",
            subscription_until=existing.subscription_until if existing else None,
            created_at=existing.created_at if existing else NOW,
            is_active=True,
            onboarded_at=existing.onboarded_at if existing else None,
        )
        self.state.users[int(telegram_id)] = user
        return user

    async def confirm_login(self, code: str, telegram_id: int) -> LoginLinkConfirmOut:
        # Мок: код считается валидным, если он непустой и не «expired».
        return LoginLinkConfirmOut(status="ok" if code and code != "expired" else "expired")


# --------------------------------------------------------------------- контейнер


@dataclass(frozen=True)
class MockServices:
    """Набор моков с общим состоянием — то, что backend-service кладёт в контейнер."""

    state: MemoryState
    users: MockUsers
    listings: MockListings
    dialog: MockDialog
    analysis: MockAnalysis
    calc: MockCalc
    billing: MockBilling
    notify: MockNotify


def build_mock_services() -> MockServices:
    state = MemoryState()
    return MockServices(
        state=state,
        users=MockUsers(state),
        listings=MockListings(),
        dialog=MockDialog(state),
        analysis=MockAnalysis(state),
        calc=MockCalc(),
        billing=MockBilling(state),
        notify=MockNotify(state),
    )
