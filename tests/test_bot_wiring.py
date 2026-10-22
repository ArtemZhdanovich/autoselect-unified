"""Сборка бота: меню по решению D2, клавиатуры, FSM-имена, Dispatcher."""

from __future__ import annotations

import pytest

from bot_service.main import build_dispatcher
from bot_service.states import ButtonForm, PriceSelection
from bot_service.ui import keyboards
from shared.contracts.bot import callbacks as cb
from shared.contracts.bot import states as contract_states
from shared.mocks.fixtures import LISTINGS


def callback_data(keyboard) -> list[str]:
    return [button.callback_data for row in keyboard.inline_keyboard for button in row]


def button_texts(keyboard) -> list[str]:
    return [button.text for row in keyboard.inline_keyboard for button in row]


def test_main_menu_has_exactly_two_buttons() -> None:
    """Решение D2: на главном экране две крупные кнопки."""
    keyboard = keyboards.main_menu_kb()
    assert len(keyboard.inline_keyboard) == 2
    assert callback_data(keyboard) == [cb.cb_menu("ai"), cb.cb_menu("more")]


def test_more_menu_keeps_all_legacy_actions_reachable() -> None:
    """Контракт: каждое прежнее действие доступно максимум за два клика."""
    data = set(callback_data(keyboards.more_menu_kb()))
    required = {
        cb.cb_menu("calc"),
        cb.cb_menu("compare"),
        cb.cb_menu("notify"),
        cb.cb_menu("subscribe"),
        cb.cb_menu("reset"),
        cb.cb_menu("help"),
        cb.cb_menu("main"),
        cb.cb_catalog(0),
        cb.cb_price_start(),
    }
    assert required <= data


def test_no_keyboard_is_empty() -> None:
    for keyboard in (
        keyboards.main_menu_kb(),
        keyboards.more_menu_kb(),
        keyboards.notify_kb(),
        keyboards.quiet_kb(),
        keyboards.subscribe_kb(),
        keyboards.price_cancel_kb(),
        keyboards.back_main_kb(),
    ):
        assert keyboard.inline_keyboard


def test_dialog_keyboard_has_turn_token_and_reset() -> None:
    reply = type("Reply", (), {"options": ["Корея", "Китай"], "finalize_ready": False})()
    keyboard = keyboards.dialog_kb(reply, turn=3, criteria={}, search_ready=False)
    data = callback_data(keyboard)
    assert data[0] == cb.cb_dialog_option(3, 0)
    assert data[1] == cb.cb_dialog_option(3, 1)
    assert cb.cb_dialog("finalize") not in data  # критерии не заполнены
    assert cb.cb_dialog("reset") in data


def test_dialog_keyboard_shows_search_when_ready() -> None:
    reply = type("Reply", (), {"options": [], "finalize_ready": False})()
    keyboard = keyboards.dialog_kb(
        reply, turn=1, criteria={"make": "Kia"}, search_ready=True
    )
    assert cb.cb_dialog("finalize") in callback_data(keyboard)


def test_subscribe_keyboard_matches_contract() -> None:
    data = callback_data(keyboards.subscribe_kb())
    assert cb.cb_sub_buy("pro", 30) in data
    assert cb.cb_sub_buy("pro", 365) in data
    assert cb.cb_sub_buy("business", 30) in data


def test_photo_card_keyboard_navigation() -> None:
    listing = LISTINGS[0]
    first = keyboards.photo_card_kb(listing, page=0, index=0, count=3, back_callback=cb.cb_catalog(0))
    data = callback_data(first)
    assert cb.cb_car_image(1, 1, 0) in data       # вправо есть
    assert cb.cb_car_image(1, -1, 0) not in data  # влево с первой — нет
    assert cb.cb_car_image_noop() in data
    assert cb.cb_analyze(1) in data
    assert cb.cb_calc(1) in data
    assert cb.cb_catalog(0) in data

    last = keyboards.photo_card_kb(listing, page=0, index=2, count=3, back_callback=cb.cb_catalog(0))
    assert cb.cb_car_image(1, 1, 0) in callback_data(last)
    assert cb.cb_car_image(1, 3, 0) not in callback_data(last)


def test_photo_counter_text() -> None:
    keyboard = keyboards.photo_card_kb(LISTINGS[0], 0, 1, 4, cb.cb_catalog(0))
    assert "📷 2/4" in button_texts(keyboard)


def test_button_flow_keyboards_cover_all_steps() -> None:
    for field in ("make", "year", "budget"):
        options = ["a", "b"]
        data = callback_data(keyboards.flow_kb(field, options))
        assert data[0] == cb.cb_flow(field, 0)
        assert cb.cb_flow_reset() in data


def test_catalog_keyboard_pagination() -> None:
    items = list(LISTINGS[:4])
    keyboard = keyboards.catalog_kb(items, page=0, has_next=True)
    data = callback_data(keyboard)
    assert cb.cb_car(1, 0) in data
    assert cb.cb_catalog(1) in data
    assert cb.cb_menu("main") in data

    without_next = keyboards.catalog_kb(items, page=0, has_next=False)
    assert cb.cb_catalog(1) not in callback_data(without_next)


def test_states_match_contract_names() -> None:
    assert ButtonForm.make.state == contract_states.state_name(
        contract_states.BUTTON_FORM_GROUP, "make"
    )
    for state_name in contract_states.BUTTON_FORM_STATES:
        assert hasattr(ButtonForm, state_name)
    assert PriceSelection.min_price.state == contract_states.state_name(
        contract_states.PRICE_SELECTION_GROUP, "min_price"
    )
    for state_name in contract_states.PRICE_SELECTION_STATES:
        assert hasattr(PriceSelection, state_name)


def test_dispatcher_builds_without_token() -> None:
    """Сборка не требует сети и BOT_TOKEN — важно для тестов и `make up-bot`."""
    dispatcher = build_dispatcher()
    assert dispatcher is not None
    assert dispatcher.storage is not None


def test_image_noop_callback_is_parsed_as_noop() -> None:
    assert isinstance(cb.parse("car_image:noop"), cb.CatalogImageNoop)


@pytest.mark.parametrize("sample", cb.NEW_SAMPLES)
def test_new_callbacks_are_reachable_from_builders(sample: str) -> None:
    """Каждое новое значение должно собираться своим билдером."""
    assert cb.parse(sample) is not None
