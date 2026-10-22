"""AI-разбор цены с карточки: `analyze:{listing_id}`."""

from __future__ import annotations

from aiogram import F, Router
from aiogram.types import CallbackQuery

from bot_service.skin import deutsche as skin
from bot_service.ui import keyboards, render
from shared.contracts.analysis import AnalysisUnavailable, QuotaExceeded
from shared.contracts.backend_port import BackendPort
from shared.contracts.bot import callbacks as cb

router = Router(name="card")


@router.callback_query(F.data.startswith("analyze:"))
async def analyze_from_card(callback: CallbackQuery, backend: BackendPort) -> None:
    """LLM-разбор: сначала «анализирую», затем результат или апселл (403)."""
    await callback.answer(skin.ANALYSIS_STARTED)
    message = callback.message
    assert message is not None

    parsed = cb.parse(callback.data)
    assert isinstance(parsed, cb.CardAnalyze)
    listing_id = parsed.listing_id
    user_id = callback.from_user.id

    notice = await message.answer(skin.ANALYSIS_STARTED)
    try:
        analysis = await backend.analyze_price(listing_id, user_id)
    except QuotaExceeded:
        await notice.edit_text(
            skin.ANALYSIS_QUOTA,
            reply_markup=keyboards.calc_kb(f"/listing/{listing_id}"),
        )
        return
    except AnalysisUnavailable:
        await notice.edit_text(skin.ANALYSIS_DOWN)
        return

    if analysis is None:
        await notice.edit_text(skin.ANALYSIS_DOWN)
        return

    listing = await backend.get_listing(listing_id)
    await notice.edit_text(
        render.analysis_text(analysis, listing),
        reply_markup=keyboards.calc_kb(f"/listing/{listing_id}"),
    )
