"""Реестр `callback_data` — единственный источник правды по кнопкам.

Почему так: `callback_data` — самая хрупкая часть контракта. Клиент шлёт ровно ту
строку, которую мы ему показали, поэтому любое расхождение «builder ↔ parser»
ломает кнопку молча. Здесь обе стороны живут рядом и проверяются round-trip'ом:

    parse(cb_menu("ai")) == Menu("ai")

Прежние значения из `auto_bot` перечислены в `LEGACY_SAMPLES` — их обязан
принимать парсер после любого рефакторинга (golden-проверка Этапа 3).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Final, TypeAlias


class UnknownCallback(ValueError):
    """Строка не принадлежит контракту — кнопка устарела или подделана."""


# --------------------------------------------------------------------------- модели


@dataclass(frozen=True, slots=True)
class Menu:
    """`menu:{action}` — главное меню и его подэкраны."""

    action: str


@dataclass(frozen=True, slots=True)
class MenuNotifySet:
    mode: str


@dataclass(frozen=True, slots=True)
class MenuQuietSet:
    value: str


@dataclass(frozen=True, slots=True)
class DialogAction:
    action: str


@dataclass(frozen=True, slots=True)
class DialogOption:
    """Кнопка-опция панели диалога; `turn` — токен хода."""

    turn: int
    index: int


@dataclass(frozen=True, slots=True)
class CardAnalyze:
    listing_id: int


@dataclass(frozen=True, slots=True)
class CardCalc:
    listing_id: int


@dataclass(frozen=True, slots=True)
class PayBuy:
    tier: str
    days: int


@dataclass(frozen=True, slots=True)
class FlowOption:
    field: str
    index: int


@dataclass(frozen=True, slots=True)
class FlowReset:
    pass


@dataclass(frozen=True, slots=True)
class CatalogPage:
    page: int


@dataclass(frozen=True, slots=True)
class CatalogCar:
    car_id: int
    page: int


@dataclass(frozen=True, slots=True)
class CatalogImage:
    car_id: int
    index: int
    page: int


@dataclass(frozen=True, slots=True)
class CatalogImageNoop:
    pass


@dataclass(frozen=True, slots=True)
class PriceStart:
    pass


@dataclass(frozen=True, slots=True)
class PriceCancel:
    pass


@dataclass(frozen=True, slots=True)
class PricePage:
    page: int


@dataclass(frozen=True, slots=True)
class PriceCar:
    car_id: int
    page: int


ParsedCallback: TypeAlias = (
    Menu
    | MenuNotifySet
    | MenuQuietSet
    | DialogAction
    | DialogOption
    | CardAnalyze
    | CardCalc
    | PayBuy
    | FlowOption
    | FlowReset
    | CatalogPage
    | CatalogCar
    | CatalogImage
    | CatalogImageNoop
    | PriceStart
    | PriceCancel
    | PricePage
    | PriceCar
)


# ------------------------------------------------------------------------- сборка

MENU_ACTIONS: Final[tuple[str, ...]] = (
    "main",      # «🔙 В главное меню» (новый, из deutsche_motors_bot)
    "more",      # «⚙️ Ещё» — второй уровень главного меню
    "ai",
    "calc",
    "compare",
    "notify",
    "quiet",
    "subscribe",
    "reset",
    "help",
)

NOTIFY_MODES: Final[tuple[str, ...]] = ("instant", "digest", "off")
QUIET_VALUES: Final[tuple[str, ...]] = ("23:00-08:00", "22:00-10:00", "off")
DIALOG_ACTIONS: Final[tuple[str, ...]] = ("reset", "restore", "finalize")
FLOW_FIELDS: Final[tuple[str, ...]] = ("make", "year", "budget")
PAY_TIERS: Final[tuple[str, ...]] = ("pro", "business")


def cb_menu(action: str) -> str:
    if action not in MENU_ACTIONS:
        raise UnknownCallback(f"menu:{action} не входит в контракт")
    return f"menu:{action}"


def cb_menu_notify_set(mode: str) -> str:
    if mode not in NOTIFY_MODES:
        raise UnknownCallback(f"режим уведомлений {mode!r} не входит в контракт")
    return f"menu:notify_set:{mode}"


def cb_menu_quiet_set(value: str) -> str:
    if value not in QUIET_VALUES:
        raise UnknownCallback(f"тихие часы {value!r} не входят в контракт")
    return f"menu:quiet_set:{value}"


def cb_dialog(action: str) -> str:
    if action not in DIALOG_ACTIONS:
        raise UnknownCallback(f"dlg:{action} не входит в контракт")
    return f"dlg:{action}"


def cb_dialog_option(turn: int, index: int) -> str:
    return f"dlg:opt:{int(turn)}:{int(index)}"


def cb_analyze(listing_id: int) -> str:
    return f"analyze:{int(listing_id)}"


def cb_calc(listing_id: int) -> str:
    return f"calc:{int(listing_id)}"


def cb_sub_buy(tier: str, days: int) -> str:
    if tier not in PAY_TIERS:
        raise UnknownCallback(f"тариф {tier!r} не входит в контракт")
    return f"sub:buy:{tier}:{int(days)}"


def cb_flow(field: str, index: int) -> str:
    if field not in FLOW_FIELDS:
        raise UnknownCallback(f"поле {field!r} не входит в контракт")
    return f"btn:{field}:{int(index)}"


def cb_flow_reset() -> str:
    return "btn:reset"


def cb_catalog(page: int) -> str:
    return f"catalog:{int(page)}"


def cb_car(car_id: int, page: int) -> str:
    return f"car:{int(car_id)}:{int(page)}"


def cb_car_image(car_id: int, index: int, page: int) -> str:
    return f"car_image:{int(car_id)}:{int(index)}:{int(page)}"


def cb_car_image_noop() -> str:
    return "car_image:noop"


def cb_price_start() -> str:
    return "price:start"


def cb_price_cancel() -> str:
    return "price:cancel"


def cb_price_page(page: int) -> str:
    return f"price_page:{int(page)}"


def cb_price_car(car_id: int, page: int) -> str:
    return f"price_car:{int(car_id)}:{int(page)}"


# ------------------------------------------------------------------------- разбор

#: Порядок важен: специфичные шаблоны проверяются раньше общих.
CALLBACK_PATTERNS: Final[tuple[tuple[str, str], ...]] = (
    ("menu_notify_set", r"^menu:notify_set:(instant|digest|off)$"),
    ("menu_quiet_set", r"^menu:quiet_set:(off|\d{2}:\d{2}-\d{2}:\d{2})$"),
    ("menu", r"^menu:(main|more|ai|calc|compare|notify|quiet|subscribe|reset|help)$"),
    ("dialog_option", r"^dlg:opt:(\d+):(\d+)$"),
    ("dialog_action", r"^dlg:(reset|restore|finalize)$"),
    ("card_analyze", r"^analyze:(\d+)$"),
    ("card_calc", r"^calc:(\d+)$"),
    ("pay_buy", r"^sub:buy:(pro|business):(\d+)$"),
    ("flow_reset", r"^btn:reset$"),
    ("flow_option", r"^btn:(make|year|budget):(\d+)$"),
    ("catalog_image_noop", r"^car_image:noop$"),
    ("catalog_image", r"^car_image:(\d+):(\d+):(\d+)$"),
    ("catalog_car", r"^car:(\d+):(\d+)$"),
    ("catalog_page", r"^catalog:(\d+)$"),
    ("price_start", r"^price:start$"),
    ("price_cancel", r"^price:cancel$"),
    ("price_page", r"^price_page:(\d+)$"),
    ("price_car", r"^price_car:(\d+):(\d+)$"),
)

_COMPILED: Final[tuple[tuple[str, re.Pattern[str]], ...]] = tuple(
    (name, re.compile(pattern)) for name, pattern in CALLBACK_PATTERNS
)


def parse(data: str | None) -> ParsedCallback:
    """Разобрать `callback_data` в типизированный объект.

    Бросает `UnknownCallback`, если строка не принадлежит контракту — вызывающая
    сторона отвечает пользователю «кнопка устарела», не роняя обработчик.
    """
    if not data:
        raise UnknownCallback("пустой callback_data")

    for name, pattern in _COMPILED:
        match = pattern.match(data)
        if match is None:
            continue
        groups = match.groups()
        if name == "menu_notify_set":
            return MenuNotifySet(groups[0])
        if name == "menu_quiet_set":
            return MenuQuietSet(groups[0])
        if name == "menu":
            return Menu(groups[0])
        if name == "dialog_option":
            return DialogOption(int(groups[0]), int(groups[1]))
        if name == "dialog_action":
            return DialogAction(groups[0])
        if name == "card_analyze":
            return CardAnalyze(int(groups[0]))
        if name == "card_calc":
            return CardCalc(int(groups[0]))
        if name == "pay_buy":
            return PayBuy(groups[0], int(groups[1]))
        if name == "flow_reset":
            return FlowReset()
        if name == "flow_option":
            return FlowOption(groups[0], int(groups[1]))
        if name == "catalog_image_noop":
            return CatalogImageNoop()
        if name == "catalog_image":
            return CatalogImage(int(groups[0]), int(groups[1]), int(groups[2]))
        if name == "catalog_car":
            return CatalogCar(int(groups[0]), int(groups[1]))
        if name == "catalog_page":
            return CatalogPage(int(groups[0]))
        if name == "price_start":
            return PriceStart()
        if name == "price_cancel":
            return PriceCancel()
        if name == "price_page":
            return PricePage(int(groups[0]))
        if name == "price_car":
            return PriceCar(int(groups[0]), int(groups[1]))

    raise UnknownCallback(f"неизвестный callback_data: {data!r}")


#: Эталонные строки из `auto_bot` (написаны руками по коду, не сгенерированы).
#: Golden-тест требует, чтобы каждая из них разбиралась без ошибки.
LEGACY_SAMPLES: Final[tuple[str, ...]] = (
    "menu:ai",
    "menu:calc",
    "menu:compare",
    "menu:notify",
    "menu:quiet",
    "menu:subscribe",
    "menu:reset",
    "menu:help",
    "menu:notify_set:instant",
    "menu:notify_set:digest",
    "menu:notify_set:off",
    "menu:quiet_set:23:00-08:00",
    "menu:quiet_set:22:00-10:00",
    "menu:quiet_set:off",
    "dlg:reset",
    "dlg:restore",
    "dlg:finalize",
    "dlg:opt:1:0",
    "dlg:opt:17:7",
    "analyze:1",
    "calc:1",
    "sub:buy:pro:30",
    "sub:buy:pro:365",
    "sub:buy:business:30",
    "btn:make:0",
    "btn:year:3",
    "btn:budget:2",
    "btn:reset",
)

#: Новые строки, добавленные вместе с UI из `deutsche_motors_bot`.
NEW_SAMPLES: Final[tuple[str, ...]] = (
    "menu:main",
    "menu:more",
    "catalog:0",
    "car:1:0",
    "car_image:1:2:0",
    "car_image:noop",
    "price:start",
    "price:cancel",
    "price_page:1",
    "price_car:1:0",
)
