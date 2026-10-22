"""Структурные шаблоны сообщений: порядок блоков и лимиты — контракт, слова — скин.

Зачем разделение: по решению D1 тексты заменяются на копирайт `deutsche_motors_bot`,
но структура (что за чем идёт, где `<b>`, какой лимит) обязана остаться прежней —
иначе парсеры клиентов и golden-тесты Этапа 3 поедут.

Функции принимают `titles`/`labels` — словарь подписей от скина. Если подпись не
передана, берётся формулировка из `auto_bot` (безопасный дефолт).
"""

from __future__ import annotations

import html
from dataclasses import dataclass
from typing import Any, Final, Mapping

from shared.contracts.bot.limits import MAX_CAPTION

#: Флаги стран — семантические маркеры, одинаковые во всех скинах.
COUNTRY_LABELS: Final[dict[str, str]] = {
    "KR": "🇰🇷 Корея",
    "CN": "🇨🇳 Китай",
    "DE": "🇩🇪 Германия",
    "US": "🇺🇸 США",
    "JP": "🇯🇵 Япония",
}

#: Порядок и подписи полей критериев. Порядок — контракт, подпись — скин.
CRITERIA_FIELDS: Final[tuple[tuple[str, str], ...]] = (
    ("make", "Марка"),
    ("model", "Модель"),
    ("year_from", "Год от"),
    ("year_to", "Год до"),
    ("price_min", "Цена от"),
    ("price_max", "Цена до"),
    ("currency", "Валюта"),
    ("mileage_max", "Пробег до, км"),
    ("fuel", "Топливо"),
    ("transmission", "КПП"),
    ("drive", "Привод"),
    ("body_type", "Кузов"),
    ("color", "Цвет"),
    ("engine_volume_min", "Объём от"),
    ("engine_volume_max", "Объём до"),
    ("country", "Страна"),
    ("location", "Локация"),
)

DEFAULT_CRITERIA_TITLES: Final[dict[str, str]] = {field: title for field, title in CRITERIA_FIELDS}


@dataclass(frozen=True, slots=True)
class CaptionLabels:
    """Подписи карточки объявления (структура строки от них не зависит)."""

    no_price: str = "цена не указана"
    source: str = "📍 Источник"
    mileage_suffix: str = "км"
    vin_prefix: str = "VIN"


def fmt_number(value: Any) -> str:
    """Число с неразрывными по смыслу пробелами: 45 000 (никогда `45,000`)."""
    try:
        return f"{float(value):,.0f}".replace(",", " ")
    except (TypeError, ValueError):
        return str(value)


def format_value(field: str, value: Any) -> str:
    """Значение критерия по-человечески: страны флагами, деньги — с пробелами."""
    if field == "country":
        return COUNTRY_LABELS.get(str(value), str(value))
    if field in ("price_min", "price_max", "mileage_max"):
        try:
            return f"{int(str(value)):,}".replace(",", " ")
        except (TypeError, ValueError):
            return str(value)
    if field == "sources" and isinstance(value, list):
        return ", ".join(str(item) for item in value)
    return str(value)


def format_criteria(
    criteria: Mapping[str, Any],
    titles: Mapping[str, str] | None = None,
) -> str:
    """Критерии списком `• Подпись: <b>значение</b>`. Никакого JSON."""
    resolved = dict(DEFAULT_CRITERIA_TITLES)
    if titles:
        resolved.update(titles)

    lines: list[str] = []
    for field, _default_title in CRITERIA_FIELDS:
        value = criteria.get(field)
        if value is None or value == "":
            continue
        title = resolved.get(field, field)
        lines.append(f"• {title}: <b>{html.escape(format_value(field, value))}</b>")

    sources = criteria.get("sources")
    if sources:
        lines.append(
            "• Источники: <b>"
            + html.escape(", ".join(str(item) for item in sources))
            + "</b>"
        )
    return "\n".join(lines)


def dialog_panel_text(
    reply_text: str,
    criteria: Mapping[str, Any],
    *,
    header: str = "📋 <b>Параметры поиска:</b>",
    titles: Mapping[str, str] | None = None,
) -> str:
    """Текст панели диалога: ответ агента + заполненные критерии (ТЗ п. 7.4)."""
    text = html.escape(reply_text).strip()
    filled = {key: value for key, value in (criteria or {}).items() if value is not None and value != []}
    if filled:
        text += f"\n\n{header}\n" + format_criteria(filled, titles)
    return text


def plural_ru(count: int, one: str, few: str, many: str) -> str:
    """Русские формы: 1 вариант / 2 варианта / 5 вариантов."""
    count %= 100
    if 11 <= count <= 14:
        return many
    count %= 10
    if count == 1:
        return one
    if 2 <= count <= 4:
        return few
    return many


def shorten(text: str, limit: int) -> str:
    """Обрезка с многоточием — для заголовков карточек и истории."""
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 1)] + "…"


def listing_caption(
    listing: Mapping[str, Any],
    labels: CaptionLabels | None = None,
) -> str:
    """Короткая карточка объявления: `<b>title</b>`, цена, спеки, источник.

    Структура повторяет `build_listing_caption` из `auto_bot` (UI/UX ТЗ §5.5):
    заголовок → цена → одна строка спек через ` · ` → источник. Обрезка до 1024.
    """
    resolved = labels or CaptionLabels()

    title = " ".join(str(x) for x in (listing.get("make"), listing.get("model")) if x) or "Автомобиль"
    price = listing.get("price")
    if price:
        currency = str(listing.get("currency") or "").strip()
        price_str = f"{fmt_number(price)} {currency}".strip()
    else:
        price_str = resolved.no_price

    details: list[str] = []
    if listing.get("body_type"):
        details.append(str(listing["body_type"]))
    if listing.get("year"):
        details.append(str(listing["year"]))
    if listing.get("mileage_km"):
        details.append(f"{fmt_number(listing['mileage_km'])} {resolved.mileage_suffix}")
    if listing.get("vin"):
        details.append(f"{resolved.vin_prefix} {listing['vin']}")

    caption = f"<b>{html.escape(title)}</b>\n💰 {html.escape(price_str)}"
    if details:
        caption += "\n⚙️ " + html.escape(" · ".join(details))
    if listing.get("source"):
        caption += f"\n{resolved.source}: {html.escape(str(listing['source']))}"
    return caption[:MAX_CAPTION]


def share_title(listing: Mapping[str, Any]) -> str:
    """Заголовок inline-результата: «Make Model, год»."""
    title = " ".join(str(x) for x in (listing.get("make"), listing.get("model")) if x) or "Автомобиль"
    if listing.get("year"):
        title = f"{title}, {listing['year']}"
    return title[:256]
