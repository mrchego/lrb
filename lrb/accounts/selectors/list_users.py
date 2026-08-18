from typing import Optional
from django.db.models import Q
from lrb.accounts.models import User
from lrb.core.pagination import paginate_queryset


def list_users(
    *,
    company_id=None,
    is_active: Optional[bool] = None,
    can_login: Optional[bool] = None,
    search: Optional[str] = None,
    limit: Optional[int] = None,
    offset: int = 0,
):
    qs = User.objects.select_related("company").all()
    if company_id:
        qs = qs.filter(company_id=company_id)
    if is_active is not None:
        qs = qs.filter(is_active=is_active)
    if can_login is not None:
        qs = qs.filter(can_login=can_login)
    if search:
        qs = qs.filter(
            Q(email__icontains=search)
            | Q(first_name__icontains=search)
            | Q(last_name__icontains=search)
        )
    return paginate_queryset(qs.order_by("-created_at"), limit=limit, offset=offset)


# 1. Purpose — Why this exists

# What problem is this solving?
# This is the actual "search/browse users" service — the backend behind a staff-facing user management screen. It needs to support filtering by company, active status, login capability, and a free-text search, all combined, then paginated — a realistic, fairly complex real-world query.

# Why not just build this query inline in the GraphQL resolver?
# Same reasoning as everything else in your service layer — resolvers should stay thin orchestration, with the actual query-building logic testable and reusable independent of GraphQL.

# When is this used?
# Directly behind a listUsers GraphQL query, probably rendering an admin/staff user management table with search and filters.

# What breaks without it?
# The filtering and pagination logic would live inside the resolver itself, mixing GraphQL concerns with business/query logic, and violating your project's service/selector separation convention.

# 2. Imports — explained like you've never programmed
# python
# from typing import Optional
# from django.db.models import Q
# from lrb.accounts.models import User
# from lrb.core.pagination import paginate_queryset

# Optional — you know this one now: "this type, or None."

# from django.db.models import Q — Q is a class Django gives you for building filter conditions that need OR logic (or complex combinations of AND/OR). Plain .filter(a=1, b=2) always means AND — there's no way to express "field A matches OR field B matches" using plain keyword arguments alone. Q objects exist specifically to be combined with | (or) and & (and) operators.

# User and paginate_queryset — both your own project's code, reached via dotted paths through your app structure, exactly as before.

# 3. Signature — every symbol explained
# python
# def list_users(
#     *,
#     company_id=None,
#     is_active: Optional[bool] = None,
#     can_login: Optional[bool] = None,
#     search: Optional[str] = None,
#     limit: Optional[int] = None,
#     offset: int = 0,
# ):

# The lone * up front — every single parameter after it is keyword-only, consistent with your project's convention.

# Worth flagging: company_id=None has no type hint, while every other parameter here does. Small inconsistency — should almost certainly read company_id: Optional[str] = None, matching the pattern used everywhere else in this exact function.

# Everything else follows a pattern you've now internalized: Optional[bool] = None for tri-state filters (unspecified / true / false — notice this is not the same as a plain bool defaulting to False, because None here specifically means "don't filter on this field at all," a third state a plain boolean can't represent), Optional[str] = None for the free-text search, Optional[int] = None for limit (deferring to clamp_page_size's default), and offset: int = 0 — mandatory type, but a real default (0 is always a valid starting offset, so there's no need for an Optional here).

# No return type hint. Given what we now know this returns — go check paginate_queryset's return value — this function returns tuple[list[User], int], and that should be written explicitly here too.

# 4. Classes

# No class — this function builds and returns one query result; no state to carry between calls.

# 5. Body — line by line
# python
# qs = User.objects.select_related("company").all()

# New piece: .select_related("company"). Read right to left in meaning: this tells Django to fetch each user's related company row in the same query, using a SQL JOIN, instead of the default behavior of running a separate query every single time some later code accesses user.company. This is a performance optimization — without it, rendering a table of 50 users, each showing their company name, would trigger 50 extra queries (one per user) instead of zero.

# .all() — explicitly means "no filtering yet, just start with everything." It's slightly redundant here since .select_related(...) alone would already give you a full, chainable queryset — but it doesn't hurt, and some people include it purely for readability, to visually mark "this is the starting point, filters come next."

# python
# if company_id:
#     qs = qs.filter(company_id=company_id)
# if is_active is not None:
#     qs = qs.filter(is_active=is_active)
# if can_login is not None:
#     qs = qs.filter(can_login=can_login)

# Three conditional narrowings, each following the exact "guard-check query" pattern you already know from count_active_superusers. Notice the deliberate difference between the first (if company_id:) and the next two (if is_active is not None:). This isn't sloppiness — it's correct, careful code: is_active and can_login are booleans, where False is a completely legitimate, meaningful filter value (someone might genuinely want "show me only inactive users"). If this had used if is_active: instead, a caller passing is_active=False would be silently ignored, since False is falsy — the filter would never apply. company_id, by contrast, is a string where an empty string never means anything meaningful, so the simpler falsy check is safe there.

# python
# if search:
#     qs = qs.filter(
#         Q(email__icontains=search)
#         | Q(first_name_icontains=search)
#         | Q(last_name_icontains=search)
#     )

# This is where the bug from the top of this response lives. Reading this as intended: "match users where the email contains the search text, OR the first name contains it, OR the last name contains it" — the | between Q(...) objects is exactly what makes OR logic possible, which plain .filter(a=..., b=...) can't express. icontains means "case-insensitive substring match."

# But as written:

# Q(email__icontains=search) — correct, double underscore.
# Q(first_name_icontains=search) — wrong, single underscore. Django parses this as one literal field name, first_name_icontains, which your User model does not have. This raises django.core.exceptions.FieldError the instant this line executes with any search value provided.
# Q(last_name_icontains=search) — same bug, single underscore.

# Fix:

# python
# if search:
#     qs = qs.filter(
#         Q(email__icontains=search)
#         | Q(first_name__icontains=search)
#         | Q(last_name__icontains=search)
#     )

# Just adding the missing underscore in each — two characters, but the difference between "this feature works" and "this feature throws a 500 error every time someone types into the search box."

# python
# return paginate_queryset(qs.order_by("-created_at"), limit=limit, offset=offset)

# Right side, read as a journey: qs.order_by("-created_at") — sort the filtered queryset by created_at, and the leading - means descending (newest first). Then this whole ordered, filtered queryset gets passed into paginate_queryset — the file we just walked through — along with the caller's limit/offset.

# Why does ordering happen here, at the very last moment, rather than at the top? Because pagination without a consistent, deterministic order is genuinely unsafe — if you paginate an unordered queryset, the database is free to return rows in a different order on each query, meaning the same user could show up on two different "pages," or vanish from all of them. Ordering right before pagination guarantees a stable, repeatable sequence across the count query and the slice query.

# Whole line: "Sort the fully-filtered users newest-first, then hand off to the shared pagination helper, and return whatever it returns (items, total_count) directly."

# 6. Beginner questions, answered proactively

# Why select_related and not prefetch_related?
# select_related is for "to-one" relationships (a user has one company) and works via SQL JOIN. prefetch_related is for "to-many" relationships (like a user having many orders) and works via a second separate query. company here is presumably a single foreign key on User, so select_related is the right tool.

# Why does company_id use a plain falsy check while is_active/can_login explicitly check is not None?
# Covered above, but worth restating as the general rule: for booleans where False is a meaningful, intentional filter value, always check is not None explicitly. For strings/IDs where an empty value is never meaningful, a plain truthy check is fine.

# Why does the ordering happen at the very end instead of right after .select_related(...).all()?
# It doesn't strictly have to be last — Django queries are lazy and chainable in any order — but placing it directly before pagination makes the dependency visually obvious to a reader: "pagination needs a stable order, so here's the order, right where it's used."

# 7. Design discussion

# Why keep all these filters as separate optional parameters instead of, say, accepting a dictionary of arbitrary filters?
# Explicit named parameters are self-documenting and type-checkable — a caller (and their editor) can see exactly which filters exist and what type each expects. A generic filters: dict would be more "flexible" but would lose all of that safety, and could silently accept typo'd filter keys that do nothing.

# Trade-off: this design doesn't scale infinitely — if this function eventually needs ten more filters, the signature gets unwieldy. At that point, a small dataclass (UserListFilters) bundling all the optional criteria together might be worth introducing, similar in spirit to your SimpleMutationPayload pattern for return values.

# 8. DIY Recipe — build one like this yourself
# Start from .select_related(...) for any foreign key you know you'll access on every result, to avoid N+1 queries.
# For each optional filter, ask: can the "off" state (False, 0, "") also be a meaningful value someone might filter by? If yes, check is not None explicitly. If no, a plain truthy check is fine.
# For free-text search across multiple fields, build a Q() chain joined with |, and double-check every __lookup has its double underscore — this is the single easiest typo to make and the hardest to catch just by eyeballing, since it "looks" right.
# Apply .order_by(...) immediately before handing off to pagination, not before — keeps the "pagination needs stable order" dependency visible.
# Delegate pagination to your shared helper rather than reimplementing count+slice here.
# 9. General pattern recognition

# This combines two patterns you already know how to name: "guard-check query" (repeated for each optional filter) feeding into "clamp, then two-query paginate" (from pagination.py). Recognizing that this file is just composing two already-familiar shapes — rather than being a wholly new kind of thing — is exactly the payoff of building this pattern vocabulary.

# 10. Real project usage

# Directly behind a GraphQL query resolver:

# python
# def resolve_users(self, info, company_id=None, is_active=None, search=None, limit=None, offset=0):
#     actor = get_current_user(info)
#     require_permission(actor=actor, codename="staff.view_users")
#     items, total = list_users(company_id=company_id or actor.company_id, is_active=is_active, search=search, limit=limit, offset=offset)
#     return UserListPayload(items=items, total_count=total)
# 11. Common beginner mistakes

# ❌ The exact bug in this file — a missing double underscore in a Q() lookup, which passes code review silently (it looks fine at a glance) and only surfaces when someone actually searches by name.

# ❌ Using if is_active: instead of if is_active is not None: — silently drops legitimate is_active=False filtering.

# ❌ Forgetting .select_related(...) on a field you know you'll render for every row, causing an N+1 query problem invisible in development (small dataset) but severe in production (many rows).

# ❌ Ordering after slicing instead of before, or forgetting .order_by(...) entirely before pagination — leads to inconsistent, duplicated, or missing rows across pages.

# 12. Think like the original developer
# What problem am I solving? "Staff need to browse and search users with several optional filters, and see a stable, paginated result."
# What inputs will I need? A handful of optional filter criteria, plus pagination controls — all independent of each other.
# What could go wrong? Forgetting a JOIN and causing N+1 queries; treating False filters as "no filter"; a typo in a multi-field OR search; unstable pagination from missing ordering.
# How should I report results? Delegate to the shared pagination helper — don't reinvent count/slice here.
# What should happen if everything works? A filtered, ordered, safely-paginated set of users, plus the true total count, ready for a GraphQL resolver to hand to the frontend.