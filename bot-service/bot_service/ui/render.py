"""Рендер сообщений: структура из контракта, слова из скина.

Никакой бизнес-логики и обращений к сети — только форматирование DTO.
Такой слой легко проверять snapshot-тестами (Этап 3).
"""

from __future__ import annotations

import html
from typing import Any, Mapping, Sequence

from bot_service.skin import deutsche as skin
from shared.contracts.analysis import AnalysisOut
from shared.contracts.bot.limits import HISTORY_MESSAGES, HISTORY_TRUNCATE
from shared.contracts.bot.templates import (
    CaptionLabels,
    dialog_panel_text,
    format_criteria,
    listing_caption,
    plural_ru,
    shorten,
)
from shared.contracts.delivery import DeliveryOut
from shared.contracts.listing import ListingOut

LABELS = CaptionLabels(**skin.CAPTION_LABELS)


def num(value: Any) -> str:
    """Число с пробелами вместо запятых — так принято в русской типографике."""
    try:
        return f"{float(value):,.0f}".replace(",", " ")
    except (TypeError, ValueError):
        return str(value)


def search_ready(criteria: Mapping[str, Any] | None) -> bool:
    """Эвристика готовности к поиску (унаследована из `auto_bot`).

    Марка/модель + бюджет + страна — без этого `dlg:finalize` не показываем.
    """
    criteria = criteria or {}
    has_car = bool(criteria.get("make") or criteria.get("model"))
    has_price = bool(criteria.get("price_max") or criteria.get("price_min"))
    has_geo = bool(criteria.get("country") or criteria.get("sources"))
    return has_car and has_price and has_geo


def criteria_text(criteria: Mapping[str, Any]) -> str:
    return format_criteria(criteria, skin.FIELD_TITLES)


def dialog_text(reply_text: str, criteria: Mapping[str, Any]) -> str:
    return dialog_panel_text(
        reply_text, criteria, header=skin.CRITERIA_HEADER, titles=skin.FIELD_TITLES
    )


def history_text(messages: Sequence[Mapping[str, Any]]) -> str:
    """Последние сообщения диалога: «кто: текст», обрезка до 160 символов."""
    recent = [m for m in messages if m.get("role") in ("user", "assistant")][-HISTORY_MESSAGES:]
    lines: list[str] = []
    for message in recent:
        who = skin.HISTORY_YOU if message.get("role") == "user" else skin.HISTORY_BOT
        text = html.escape(str(message.get("content", "")).strip())
        lines.append(f"{who}: {shorten(text, HISTORY_TRUNCATE)}")
    return "\n\n".join(lines)


def caption(listing: ListingOut) -> str:
    """Фото-подпись карточки: `<b>title</b>`, цена, спеки, источник."""
    return listing_caption(listing.model_dump(), LABELS)


def calc_text(out: DeliveryOut) -> str:
    """Смета «под ключ»: шапка → компоненты → итог → примечание → дисклеймер."""
    header = (
        f"Авто {num(out.price_usd)} $ · {out.engine_cc} см³ · "
        f"{out.year} г. ({out.age_group})"
    )
    lines = [skin.CALC_TITLE, "", header]
    for component in out.components or []:
        label = component.get("label") or component.get("name") or ""
        rub = component.get("rub", component.get("value_rub", 0))
        lines.append(f"• {label}: {num(rub)} ₽")
    lines.append("")
    lines.append(f"<b>Итого: ~{num(out.total_rub)} ₽ (~{num(out.total_usd)} $)</b>")
    if out.util_note:
        lines.append(f"\n⚠️ {out.util_note}")
    lines.append(f"\n{skin.CALC_DISCLAIMER}")
    return "\n".join(lines)


def compare_text(items: Sequence[Mapping[str, Any]]) -> str:
    """Сравнение вариантов: медали, дельта к лучшему, дисклеймер."""
    medals = ("🥇", "🥈", "🥉", "4️⃣", "5️⃣")
    best = float(items[0]["total_usd"]) if items else 0.0
    lines = [skin.COMPARE_TITLE]
    for index, item in enumerate(items):
        mark = medals[index] if index < len(medals) else "•"
        line = (
            f"{mark} <b>{html.escape(str(item.get('title', '')))}</b>\n"
            f"     {num(item.get('price_usd', 0))} $ → "
            f"<b>~{num(item.get('total_usd', 0))} $</b>"
        )
        if index > 0 and best:
            delta = float(item.get("total_usd", 0)) - best
            line += f" (+{num(delta)} $)"
        lines.append(line + "\n")
    lines.append(skin.COMPARE_DISCLAIMER)
    return "\n".join(lines)


def analysis_text(analysis: AnalysisOut, listing: ListingOut | None = None) -> str:
    """AI-разбор: цена → рынок → вердикт → диапазон → дельта → факторы → апселл."""
    verdict, hint = skin.VERDICTS.get(analysis.verdict, skin.VERDICTS["fair"])
    currency = analysis.currency or ""
    title = ""
    if listing is not None:
        name = " ".join(str(x) for x in (listing.make, listing.model) if x)
        if listing.year:
            name += f", {listing.year}"
        title = f"{name}\n" if name else ""

    lines = [f"{skin.ANALYSIS_TITLE}\n{title}"]
    if analysis.price:
        lines.append(f"💵 Цена: {num(analysis.price)} {currency}")
    comps = analysis.comps or {}
    if comps.get("median"):
        lines.append(
            f"📊 Рынок: {comps.get('count', 0)} сопоставимых · медиана {num(comps['median'])} {currency}"
        )
    lines.append(f"\nВердикт: {verdict}")
    if analysis.fair_min and analysis.fair_max:
        lines.append(
            f"Справедливый диапазон: <b>{num(analysis.fair_min)}–{num(analysis.fair_max)} {currency}</b>"
        )
        if analysis.price:
            middle = (analysis.fair_min + analysis.fair_max) / 2
            delta = (analysis.price - middle) / middle * 100
            arrow = "📉" if delta < 0 else "📈"
            sign = "+" if delta >= 0 else "−"
            lines.append(f"{arrow} Цена {hint}: {sign}{abs(delta):.0f}% от середины")
    if analysis.summary:
        lines.append(f"\n💬 {analysis.summary}")
    if analysis.factors:
        lines.append("\n" + "\n".join(f"• {factor}" for factor in analysis.factors[:4]))
    lines.append(f"\n{skin.ANALYSIS_QUOTA_HINT}")
    return "\n".join(lines)


def found_many(total: int) -> str:
    return skin.SEARCH_FOUND_MANY.format(
        total=total, plural=plural_ru(total, "вариант", "варианта", "вариантов")
    )


def found_few(total: int) -> str:
    return skin.SEARCH_FOUND_FEW.format(
        total=total, plural=plural_ru(total, "вариант", "варианта", "вариантов")
    )
