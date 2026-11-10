
from datetime import datetime, timezone

from models import MODELS
from usage_manager import get_usage_summary
from quota_config import QUOTA_LIMITS


def get_quota_period_start(period):
    now = datetime.now(timezone.utc)

    if period == "day":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    elif period == "month":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    elif period == "all_time":
        return None
    else:
        raise ValueError(
            "El periodo de cuota debe ser day, month o all_time."
        )

    return start.isoformat()


def get_model_quotas():
    quotas = {}
    usage_by_period = {}

    for provider, models in MODELS.items():

        for model in models:

            if not model.get("enabled", True):
                continue

            model_id = model["id"]
            key = f"{provider}/{model_id}"

            limits = dict(QUOTA_LIMITS.get(key, {}))
            limits.setdefault("requests", None)
            limits.setdefault("total_tokens", None)
            limits.setdefault("period", "month")

            period = limits["period"]
            if period not in usage_by_period:
                usage_by_period[period] = get_usage_summary(
                    since=get_quota_period_start(period)
                )

            consumption = usage_by_period[period].get(key, {
                "requests": 0,
                "successful": 0,
                "failed": 0,
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0
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


