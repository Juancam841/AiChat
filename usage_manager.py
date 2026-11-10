

from database import get_connection
from datetime import datetime, timezone


def record_usage(
    provider,
    model,
    prompt_tokens=0,
    completion_tokens=0,
    success=True,
    web_search_requests=0,
    browser_open_requests=0
):
    prompt_tokens = prompt_tokens or 0
    completion_tokens = completion_tokens or 0
    web_search_requests = web_search_requests or 0
    browser_open_requests = browser_open_requests or 0

    total_tokens = prompt_tokens + completion_tokens

    now = datetime.now(timezone.utc).isoformat()

    connection = get_connection()

    try:
        connection.execute("""
            INSERT INTO usage_records (
                provider,
                model,
                prompt_tokens,
                completion_tokens,
                total_tokens,
                success,
                created_at,
                web_search_requests,
                browser_open_requests
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            provider,
            model,
            prompt_tokens,
            completion_tokens,
            total_tokens,
            1 if success else 0,
            now,
            web_search_requests,
            browser_open_requests
        ))

        connection.commit()

    finally:
        connection.close()


def get_usage_summary(since=None):

    connection = get_connection()

    try:
        query = """
            SELECT
                provider,
                model,
                COUNT(*) AS requests,
                SUM(success) AS successful,
                SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) AS failed,
                SUM(prompt_tokens) AS prompt_tokens,
                SUM(completion_tokens) AS completion_tokens,
                SUM(total_tokens) AS total_tokens,
                SUM(web_search_requests) AS web_search_requests,
                SUM(browser_open_requests) AS browser_open_requests
            FROM usage_records
        """
        parameters = ()

        if since is not None:
            query += " WHERE created_at >= ?"
            parameters = (since,)

        query += " GROUP BY provider, model"
        rows = connection.execute(query, parameters).fetchall()

        return {
            f"{row['provider']}/{row['model']}": {
                "requests": row["requests"],
                "successful": row["successful"],
                "failed": row["failed"],
                "prompt_tokens": row["prompt_tokens"],
                "completion_tokens": row["completion_tokens"],
                "total_tokens": row["total_tokens"],
                "web_search_requests": row["web_search_requests"],
                "browser_open_requests": row["browser_open_requests"]
            }
            for row in rows
        }

    finally:
        connection.close()
