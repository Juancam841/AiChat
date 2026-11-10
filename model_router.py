
from models import MODELS

from config import PROVIDERS

from quota_manager import get_model_quotas, is_quota_available


DEFAULT_STRATEGY = "free_first"


def get_model_candidates(
    capability="general",
    strategy=DEFAULT_STRATEGY,
    exclude=None,
    supports_tools=None,
    native_web_search=None,
    web_search_cost=None
):

    candidates = []

    exclude = exclude or []

    # Consultar todas las cuotas una sola vez.
    quotas = get_model_quotas()

    for provider, models in MODELS.items():

        if not PROVIDERS.get(provider):
            continue

        for model in models:

            if not model.get("enabled", True):
                continue

            if capability not in model.get("capabilities", []):
                continue

            if (
                supports_tools is not None
                and model.get("supports_tools", False) != supports_tools
            ):
                continue

            if (
                native_web_search is not None
                and model.get("native_web_search", False) != native_web_search
            ):
                continue

            if (
                web_search_cost is not None
                and model.get("web_search_cost", "unknown") != web_search_cost
            ):
                continue

            key = f"{provider}/{model['id']}"

            quota = quotas.get(key)

            if not is_quota_available(quota):
                continue

            candidate = {
                "provider": provider,
                "model": model["id"],
                "cost_tier": model.get("cost_tier", "unknown"),
                "supports_tools": model.get("supports_tools", False),
                "native_web_search": model.get("native_web_search", False),
                "web_search_cost": model.get("web_search_cost", "unknown")
            }

            if (
                candidate["provider"],
                candidate["model"]
            ) in exclude:
                continue

            candidates.append(candidate)

    if not candidates:
        raise ValueError(
            "No hay modelos disponibles para: " + capability
        )

    if strategy == "free_first":

        candidates.sort(
            key=lambda item: item["cost_tier"] != "free"
        )

    elif strategy != "best_available":

        raise ValueError(
            f"Estrategia desconocida: {strategy}"
        )

    return candidates


def select_model(
    capability="general",
    strategy=DEFAULT_STRATEGY
):

    candidates = get_model_candidates(
        capability=capability,
        strategy=strategy
    )

    return {
        "provider": candidates[0]["provider"],
        "model": candidates[0]["model"]
    }

