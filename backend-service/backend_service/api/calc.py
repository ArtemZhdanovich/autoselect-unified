"""Калькулятор «под ключ»: `/api/calc/delivery`, `/api/calc/compare`."""

from __future__ import annotations

from fastapi import APIRouter

from backend_service.api.deps import ContainerDep
from shared.contracts.delivery import CompareIn, CompareOut, DeliveryIn, DeliveryOut

router = APIRouter(prefix="/api/calc", tags=["calc"])


@router.post("/delivery", response_model=DeliveryOut)
async def calc_delivery(payload: DeliveryIn, container: ContainerDep) -> DeliveryOut:
    """Смета «авто + море + брокер + СБКТС/ЭПТС + пошлина + сборы + утиль»."""
    return await container.calc.delivery(
        payload.price_usd,
        payload.engine_cc,
        payload.year,
        power_hp=payload.power_hp,
        region=payload.region,
    )


@router.post("/compare", response_model=CompareOut)
async def calc_compare(payload: CompareIn, container: ContainerDep) -> CompareOut:
    """Сравнить варианты «под ключ» — ответ отсортирован по итоговой сумме."""
    return await container.calc.compare(payload.items)
