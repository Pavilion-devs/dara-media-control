from __future__ import annotations

from decimal import Decimal

from genblaze_core import Asset, ModelRegistry, Modality
from genblaze_core.models.step import Step
from genblaze_core.providers.pricing import PricingContext

from .models import CostEstimate, Price, RunPlan, money


PriceSource = dict[str, Price] | ModelRegistry


def registry_step_cost(
    plan: RunPlan,
    step_index: int,
    registry: ModelRegistry,
) -> Decimal | None:
    planned = plan.steps[step_index]
    strategy = registry.get(planned.model).pricing
    if strategy is None:
        return None
    try:
        modality = Modality(planned.modality)
    except ValueError:
        modality = Modality.IMAGE
    step = Step(
        provider=planned.provider,
        model=planned.model,
        modality=modality,
    )
    assets = tuple(
        Asset(
            url=f"estimate://{planned.model}/{index}",
            media_type="application/octet-stream",
        )
        for index in range(planned.units * plan.variants)
    )
    value = strategy(PricingContext(step=step, assets=assets))
    return money(value) if value is not None else None


def estimate_run_cost(
    plan: RunPlan,
    prices: PriceSource,
) -> CostEstimate:
    per_step: list[Decimal | None] = []
    unpriced: list[str] = []
    expected = money(0)

    for index, step in enumerate(plan.steps):
        if isinstance(prices, ModelRegistry):
            step_cost = registry_step_cost(plan, index, prices)
        else:
            price = prices.get(step.model)
            step_cost = (
                money(price.per_unit_usd * step.units * plan.variants)
                if price is not None and price.per_unit_usd is not None
                else None
            )
        per_step.append(step_cost)
        if step_cost is None:
            unpriced.append(step.model)
        else:
            expected += step_cost

    expected = money(expected)
    return CostEstimate(
        expected_usd=expected,
        worst_case_usd=money(expected * plan.max_attempts),
        per_step_usd=tuple(per_step),
        unpriced_models=tuple(dict.fromkeys(unpriced)),
    )
