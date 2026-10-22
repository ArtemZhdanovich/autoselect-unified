"""Контракт `callback_data`: сборка ↔ разбор, прежние значения, отсутствие коллизий."""

from __future__ import annotations

import re

import pytest

from shared.contracts.bot import callbacks as cb


def test_build_and_parse_roundtrip() -> None:
    cases = [
        (cb.Menu("ai"), cb.cb_menu("ai")),
        (cb.Menu("main"), cb.cb_menu("main")),
        (cb.Menu("more"), cb.cb_menu("more")),
        (cb.MenuNotifySet("digest"), cb.cb_menu_notify_set("digest")),
        (cb.MenuQuietSet("23:00-08:00"), cb.cb_menu_quiet_set("23:00-08:00")),
        (cb.DialogAction("finalize"), cb.cb_dialog("finalize")),
        (cb.DialogOption(3, 1), cb.cb_dialog_option(3, 1)),
        (cb.CardAnalyze(42), cb.cb_analyze(42)),
        (cb.CardCalc(7), cb.cb_calc(7)),
        (cb.PayBuy("pro", 365), cb.cb_sub_buy("pro", 365)),
        (cb.FlowOption("budget", 2), cb.cb_flow("budget", 2)),
        (cb.FlowReset(), cb.cb_flow_reset()),
        (cb.CatalogPage(0), cb.cb_catalog(0)),
        (cb.CatalogCar(1, 2), cb.cb_car(1, 2)),
        (cb.CatalogImage(1, 2, 0), cb.cb_car_image(1, 2, 0)),
        (cb.CatalogImageNoop(), cb.cb_car_image_noop()),
        (cb.PriceStart(), cb.cb_price_start()),
        (cb.PriceCancel(), cb.cb_price_cancel()),
        (cb.PricePage(1), cb.cb_price_page(1)),
        (cb.PriceCar(1, 0), cb.cb_price_car(1, 0)),
    ]
    for expected, raw in cases:
        assert cb.parse(raw) == expected, raw


@pytest.mark.parametrize("raw", cb.LEGACY_SAMPLES)
def test_legacy_sample_is_accepted(raw: str) -> None:
    """Ни одно прежнее значение не должно перестать разбираться."""
    assert cb.parse(raw) is not None


@pytest.mark.parametrize("raw", cb.NEW_SAMPLES)
def test_new_sample_is_accepted(raw: str) -> None:
    assert cb.parse(raw) is not None


@pytest.mark.parametrize("raw", cb.LEGACY_SAMPLES + cb.NEW_SAMPLES)
def test_sample_matches_exactly_one_pattern(raw: str) -> None:
    """Два совпавших шаблона = неоднозначный разбор. Такого быть не должно."""
    matched = [name for name, pattern in cb.CALLBACK_PATTERNS if re.match(pattern, raw)]
    assert len(matched) == 1, f"{raw!r} совпал с {matched}"


@pytest.mark.parametrize(
    "raw",
    ["", None, "menu:unknown", "menu:", "catalog:", "car:1", "catalog:1:2", "admin:menu", "btn:model:0", "price:"],
)
def test_unknown_is_rejected(raw: str | None) -> None:
    with pytest.raises(cb.UnknownCallback):
        cb.parse(raw)


def test_quiet_hours_value_keeps_colons() -> None:
    """Значение содержит `:` внутри — разбор обязан резать только по первым двум."""
    parsed = cb.parse("menu:quiet_set:23:00-08:00")
    assert isinstance(parsed, cb.MenuQuietSet)
    assert parsed.value == "23:00-08:00"


def test_menu_main_is_new_not_legacy() -> None:
    """`menu:main` пришёл из deutsche_motors_bot — фиксируем, что он новый."""
    assert "menu:main" not in cb.LEGACY_SAMPLES
    assert "menu:main" in cb.NEW_SAMPLES


@pytest.mark.parametrize(
    "builder,args",
    [
        (cb.cb_menu, ("unknown",)),
        (cb.cb_sub_buy, ("gold", 30)),
        (cb.cb_flow, ("model", 0)),
        (cb.cb_dialog, ("unknown",)),
        (cb.cb_menu_notify_set, ("often",)),
    ],
)
def test_builder_rejects_values_outside_contract(builder, args) -> None:
    with pytest.raises(cb.UnknownCallback):
        builder(*args)


def test_no_duplicate_patterns() -> None:
    patterns = [pattern for _name, pattern in cb.CALLBACK_PATTERNS]
    assert len(patterns) == len(set(patterns))
