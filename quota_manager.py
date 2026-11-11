
from datetime import datetime, timedelta, timezone
import uuid

from database import get_connection
from models import MODELS
from usage_manager import get_active_reservation_summary, get_usage_summary
from quota_config import QUOTA_LIMITS


RESERVATION_TTL_MINUTES = 120


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
    reservations_by_period = {}

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
                reservations_by_period[period] = get_active_reservation_summary(
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
            reservations = reservations_by_period[period].get(key, {
                "pending_requests": 0,
                "reserved_tokens": 0
            })

            quotas[key] = {
                "provider": provider,
                "model": model_id,
                "cost_tier": model.get("cost_tier", "unknown"),
                "limits": dict(limits),
                "consumption": consumption,
                "reservations": reservations
            }

    return quotas


def is_quota_available(quota):

    if quota is None:
        return False

    limits = quota["limits"]
    consumption = quota["consumption"]

    max_requests = limits.get("requests")
    max_tokens = limits.get("total_tokens")
    reservations = quota.get("reservations", {})

    if (
        max_requests is not None
        and consumption["requests"] + reservations.get("pending_requests", 0)
        >= max_requests
    ):
        return False

    if (
        max_tokens is not None
        and consumption["total_tokens"] + reservations.get("reserved_tokens", 0)
        >= max_tokens
    ):
        return False

    return True


def reserve_model_request(provider, model):
    """Atomically reserve quota immediately before a provider API call."""
    key = f"{provider}/{model}"
    limits = dict(QUOTA_LIMITS.get(key, {}))
    limits.setdefault("requests", None)
    limits.setdefault("total_tokens", None)
    limits.setdefault("period", "month")

    max_requests = limits["requests"]
    max_tokens = limits["total_tokens"]
    if max_requests is None and max_tokens is None:
        return None

    period_start = get_quota_period_start(limits["period"])
    now = datetime.now(timezone.utc)
    now_text = now.isoformat()
    expires_at = (now + timedelta(minutes=RESERVATION_TTL_MINUTES)).isoformat()
    reservation_id = str(uuid.uuid4())
    connection = get_connection()

    try:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(
            "DELETE FROM quota_reservations WHERE expires_at <= ?",
            (now_text,)
        )

        usage_query = """
            SELECT COUNT(*) AS requests,
                   COALESCE(SUM(total_tokens), 0) AS total_tokens
            FROM usage_records
            WHERE provider = ? AND model = ?
        """
        usage_parameters = [provider, model]
        if period_start is not None:
            usage_query += " AND created_at >= ?"
            usage_parameters.append(period_start)
        usage = connection.execute(
            usage_query, usage_parameters
        ).fetchone()

        pending_query = """
            SELECT COUNT(*) AS requests,
                   COALESCE(SUM(reserved_tokens), 0) AS reserved_tokens
            FROM quota_reservations
            WHERE provider = ? AND model = ? AND expires_at > ?
        """
        pending_parameters = [provider, model, now_text]
        if period_start is not None:
            pending_query += " AND created_at >= ?"
            pending_parameters.append(period_start)
        pending = connection.execute(
            pending_query, pending_parameters
        ).fetchone()

        if (
            max_requests is not None
            and usage["requests"] + pending["requests"] >= max_requests
        ):
            raise ValueError(
                f"El modelo {key} alcanzó su límite local de solicitudes."
            )

        reserved_tokens = 0
        if max_tokens is not None:
            remaining_tokens = (
                max_tokens
                - usage["total_tokens"]
                - pending["reserved_tokens"]
            )
            if remaining_tokens <= 0:
                raise ValueError(
                    f"El modelo {key} alcanzó su límite local de tokens."
                )
            # El token disponible queda reservado para esta llamada. Esto
            # serializa llamadas con cuota de tokens hasta conocer su uso real.
            reserved_tokens = remaining_tokens

        connection.execute("""
            INSERT INTO quota_reservations (
                id, provider, model, reserved_tokens, created_at, expires_at
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            reservation_id, provider, model, reserved_tokens, now_text, expires_at
        ))
        connection.commit()
        return reservation_id
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def is_model_available(provider, model):

    key = f"{provider}/{model}"

    quotas = get_model_quotas()

    return is_quota_available(quotas.get(key))


