
from models import MODELS
from usage_manager import get_usage_summary
from quota_config import QUOTA_LIMITS


def get_model_quotas():

    usage = get_usage_summary()

    quotas = {}

    for provider, models in MODELS.items():

        for model in models:

            if not model.get("enabled", True):
                continue

            model_id = model["id"]
            key = f"{provider}/{model_id}"

            consumption = usage.get(key, {
                "requests": 0,
                "successful": 0,
                "failed": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0
            })

            limits = QUOTA_LIMITS.get(key, {
                "requests": None,
                "total_tokens": None
            })

            quotas[key] = {
                "provider": provider,
                "model": model_id,
                "cost_tier": model.get("cost_tier", "unknown"),
                "limits": dict(limits),
                "consumption": consumption
            }

    return quotas


def is_quota_available(quota):

    if quota is None:
        return False

    limits = quota["limits"]
    consumption = quota["consumption"]

    max_requests = limits.get("requests")
    max_tokens = limits.get("total_tokens")

    if (
        max_requests is not None
        and consumption["requests"] >= max_requests
    ):
        return False

    if (
        max_tokens is not None
        and consumption["total_tokens"] >= max_tokens
    ):
        return False

    return True


def is_model_available(provider, model):

    key = f"{provider}/{model}"

    quotas = get_model_quotas()

    return is_quota_available(quotas.get(key))


