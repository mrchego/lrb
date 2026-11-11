from celery import shared_task


@shared_task(name="lrb.core.cache.refresh_entry", ignore_result=True)
def refresh_cache_entry(*, policy_name: str, company_id: str, params: dict, lock_token: str) -> None:
    """Recompute one stale cache entry in the background (see read.refresh_entry)."""
    from lrb.core.cache.read import refresh_entry

    refresh_entry(
        policy_name=policy_name, company_id=company_id, params=params, lock_token=lock_token
    )
