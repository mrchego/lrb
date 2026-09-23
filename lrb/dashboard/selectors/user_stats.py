from lrb.accounts.models import User


def get_user_stats(*, company_id:str):
    qs = User.objects.filter(company_id=company_id)
    total = qs.count()
    active = qs.filter(is_active=True).count()
    locked = sum(1 for u in qs.filter(locked_until__isnull=False) if u.is_locked)
 