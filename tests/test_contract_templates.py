"""Шаблоны сообщений: структура и лимиты не должны разъезжаться."""

from __future__ import annotations

from shared.contracts.bot import limits, templates


def test_caption_structure_and_limit() -> None:
    listing = {
        "id": 1,
        "make": "Hyundai",
        "model": "Palisade",
        "year": 2023,
        "price": 52000,
        "currency": "USD",
        "mileage_km": 28000,
        "body_type": "SUV",
        "vin": "KMH8P8AB1NU100001",
        "source": "encar",
    }
    caption = templates.listing_caption(listing)
    assert caption.startswith("<b>Hyundai Palisade</b>")
    assert "💰 52 000 USD" in caption
    assert "⚙️ SUV · 2023 · 28 000 км · VIN KMH8P8AB1NU100001" in caption
    assert caption.endswith("📍 Источник: encar")
    assert len(caption) <= limits.MAX_CAPTION


def test_caption_is_truncated_to_telegram_limit() -> None:
    listing = {
        "make": "X" * 2000,
        "model": "Y" * 2000,
        "price": 1,
        "currency": "USD",
        "source": "encar",
    }
    assert len(templates.listing_caption(listing)) == limits.MAX_CAPTION


def test_caption_without_price_uses_placeholder() -> None:
    caption = templates.listing_caption({"make": "Kia", "model": "K5"})
    assert "цена не указана" in caption


def test_criteria_human_readable_and_ordered() -> None:
    text = templates.format_criteria(
        {"make": "Hyundai", "year_from": 2022, "price_max": 45000, "country": "KR"}
    )
    assert "{" not in text and "}" not in text  # никакого JSON
    assert "• Марка: <b>Hyundai</b>" in text
    assert "45 000" in text
    assert "🇰🇷 Корея" in text
    # порядок полей — контракт: марка раньше года, год раньше цены
    assert text.index("Марка") < text.index("Год от") < text.index("Цена до")


def test_criteria_skips_empty_values() -> None:
    assert templates.format_criteria({"make": None, "model": "", "sources": []}) == ""


def test_criteria_sources_line() -> None:
    text = templates.format_criteria({"sources": ["encar", "kcar"]})
    assert "Источники: <b>encar, kcar</b>" in text


def test_dialog_panel_escapes_agent_text() -> None:
    text = templates.dialog_panel_text("<script>", {"make": "Kia"})
    assert "&lt;script&gt;" in text
    assert "<b>Kia</b>" in text


def test_plural_forms() -> None:
    assert templates.plural_ru(1, "вариант", "варианта", "вариантов") == "вариант"
    assert templates.plural_ru(3, "вариант", "варианта", "вариантов") == "варианта"
    assert templates.plural_ru(11, "вариант", "варианта", "вариантов") == "вариантов"
    assert templates.plural_ru(21, "вариант", "варианта", "вариантов") == "вариант"


def test_shorten_keeps_limit() -> None:
    assert templates.shorten("abcdef", 4) == "abc…"
    assert templates.shorten("abc", 10) == "abc"
