from lrb.core.constants import DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE

def clamp_page_size(limit=None):
    """Keeps requested page sizes within DEFAULT_PAGE_SIZE..MAX_PAGE_SIZE,
    so a caller can never request an unbounded slice."""
    if limit is None:
        return DEFAULT_PAGE_SIZE
    return max(1, min(limit, MAX_PAGE_SIZE))

def paginate_queryset(queryset, *, limit=None, offset=0):
    """
    Evaluates `.count()` once, then slices — two queries total, never the
    full table. Returns (items, total_count) so GraphQL can expose both
    the page and how many rows exist in total (for a "Page X of Y" UI).
    """
    size = clamp_page_size(limit)
    offset = max(0, offset or  0)
    total_count = queryset.count()
    items = list(queryset[offset : offset + size])
    return items, total_count