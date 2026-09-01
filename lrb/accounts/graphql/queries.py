from __future__ import annotations
from typing import Optional
import strawberry
from lrb.accounts.graphql.types import UserConnection, UserType
from lrb.accounts.selectors.get_current_user import get_current_user
from lrb.accounts.selectors.get_user import get_user
from lrb.accounts.selectors.list_users import list_users
from lrb.authorization.decorators import require_owner
from lrb.core.exceptions import AppPermissionDeniedError


@strawberry.type
class UserQuery:
    @strawberry.field
    def me(self, info: strawberry.Info) -> Optional[UserType]:
        return get_current_user(info)

    @strawberry.field
    @require_owner()
    def user(self, info: strawberry.Info, user_id: strawberry.ID) -> Optional[UserType]:
        return get_user(user_id=user_id)

    @strawberry.field
    @require_owner()
    def users(
        self,
        info: strawberry.Info,
        is_active: Optional[bool] = None,
        can_login: Optional[bool] = None,
        search: Optional[str] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> UserConnection:
        current = get_current_user(info)
        if not current or not current.company_id:
            raise AppPermissionDeniedError("No company context.")
        items, total_count = list_users(
            company_id=str(current.company_id),
            is_active=is_active,
            can_login=can_login,
            search=search,
            limit=limit,
            offset=offset,
        )
        return UserConnection(items=items, total_count=total_count)



# from __future__ import annotations
# from typing import Optional
# import strawberry
# from lrb.accounts.graphql.types import UserConnection, UserType
# from lrb.accounts.selectors.get_current_user import get_current_user
# from lrb.accounts.selectors.get_user import get_user
# from lrb.accounts.selectors.list_users import list_users
# from lrb.authorization.decorators import require_owner
# from lrb.core.exceptions import AppPermissionDeniedError

# Nothing structurally new — but notice the pattern by now: three selectors imports (get_current_user, get_user, list_users), each its own file, each presumably a small read-only function. This is your service/selector separation rule in action: this GraphQL file never touches the database directly — it only calls selectors, which do the actual querying.

# class UserQuery:
# python
# @strawberry.type
# class UserQuery:

# This is a @strawberry.type used a bit differently than before: instead of representing a piece of data (like UserType or ImageType), this class represents a collection of query endpoints — each @strawberry.field method inside it becomes one thing a client can ask for at the top level of a GraphQL query (like { me { ... } } or { users { ... } }). This class is likely combined with other similar *Query classes elsewhere (e.g. OrderQuery, CompanyQuery) into one big root Query type in your config/schema.py.

# me — no permission check needed
# python
# @strawberry.field
# def me(self, info: strawberry.Info) -> Optional[UserType]:
#     return get_current_user(info)

# Signature

# info: strawberry.Info — same info object you saw inside the decorators' wrapper function, now explicitly type-hinted as strawberry.Info (Strawberry's own class for this request-context object).
# -> Optional[UserType] — returns a UserType, or None if there's no logged-in user.

# Why no @require_owner() or @require_permission() here?
# Think about what "me" means: it's "tell me about myself." Every logged-in user, no matter their role or permissions, should be able to see their own profile — there's nothing to gate. This is a deliberate, meaningful absence of a decorator, not an oversight — contrast this with user and users right below, which do need gating because they expose other people's data.

# user — a single user, by ID, owner-only
# python
# @strawberry.field
# @require_owner()
# def user(self, info: strawberry.Info, user_id: strawberry.ID) -> Optional[UserType]:
#     return get_user(user_id=user_id)

# Stacked decorators, bottom-up again
# @require_owner() wraps the real function first (adding the auth/permission gate), then @strawberry.field wraps that result, registering the gated version as the actual GraphQL field. So the order you read them top-to-bottom is the reverse of the order they apply — this is worth internalizing as a general Python rule: decorators stack like nested parentheses, closest-to-the-function applies first.

# Signature
# user_id: strawberry.ID — a plain, required parameter (no Optional, no default) — a client must supply this to call this field: { user(userId: "42") { ... } }. Notice Strawberry automatically converts Python's user_id (snake_case) into userId (camelCase) in the actual GraphQL schema — this is a Strawberry convention worth knowing, since GraphQL community style prefers camelCase while Python style prefers snake_case; you don't have to do this translation yourself.

# Body
# return get_user(user_id=user_id) — one line, delegating entirely to the selector. This is about as "thin" as a resolver can get — exactly the resolver-is-just-orchestration principle from your project conventions.

# users — the bug, and the real logic
# python
# @strawberry.field
# @require_owner()
# def users(
#     self,
#     info: strawberry.Info,
#     is_active: Optional[bool] = None,
#     can_login: Optional[bool] = None,
#     search: Optional[str] = None,
#     limit: Optional[int] = None,
#     offset: int = 0,
# ) -> UserConnection:

# Signature — the filtering pattern
# This is a new, important pattern: a query with optional filters. Each Optional[X] = None parameter (is_active, can_login, search, limit) means "the client may narrow the results by this, but doesn't have to." offset: int = 0 (not Optional) means "always a real number, defaulting to the start (0) if not specified" — same "default, not absence" idea you learned from duration_minutes: int = 15 a few files back. This lets one query support many different use cases: "show me all inactive users," "search for 'smith'," "show 20 users starting from position 40" — all through the same endpoint, just by combining different optional arguments.

# Body

# python
# current = get_current_user(info)
# if not current or not current.company_id:
#     raise AppPermissionDeniedError("No company context.")
# current = get_current_user(info) — reuses the same selector as the me field above (another example of not duplicating logic).
# if not current or not current.company_id: — two conditions joined by or: fail if there's no logged-in user at all, or if they exist but have no company_id set. Remember company_id from way back — the cheap, no-query way to check a foreign key. This connects to Role being scoped per-company: you can't list "users in my company" if the system doesn't know what company you belong to.
# raise AppPermissionDeniedError(...) — same custom exception used by your decorators, kept consistent across the codebase.
# python
# items, total_count = list_users(
#     company_id=str(current.company_id),
#     is_active=is_active,
#     can_login=can_login,
#     search=search,
#     limit=limit,
#     offset=offset,
# )
# return UserConnection(items=items, total_count=total_count)
# items, total_count = list_users(...) — this is tuple unpacking: list_users(...) returns two values at once (packaged as a tuple, like (some_list, 42)), and this line splits them into two separate names in one step, instead of writing result = list_users(...) then items = result[0] and total_count = result[1] separately.
# company_id=str(current.company_id) — explicitly converts to a string with str(...). This is a small but deliberate detail: current.company_id is likely a database integer, but the selector probably expects a string (perhaps because GraphQL IDs are always strings, or because it's compared against a string elsewhere) — converting explicitly at the boundary avoids subtle type-mismatch bugs.
# return UserConnection(items=items, total_count=total_count) — builds the UserConnection type from your very first file, completing the pagination pattern you learned there: a page of items plus the total_count for building page controls.
# The bug: require_owner() on users

# Here's the subtle issue, and it's a genuinely important one to catch as a learner. Look at the body of users again: it explicitly checks current.company_id and scopes the query with company_id=str(current.company_id). This strongly suggests the intent is: "any authenticated staff member can list users, but only within their own company." That's a company-scoped list, not an owner-only action.

# But the decorator says @require_owner() — which, from your last file, means only superusers can call this at all. That's a much stricter, different rule than "any user, scoped to their company." If the intent really was company-scoped access for regular staff, this should almost certainly be @require_permission("some_view_users_codename") instead of @require_owner() — otherwise, all that careful company-scoping logic in the body is dead weight, because non-superusers are rejected by the decorator before the function body ever runs at all.

# This is worth remembering as a general lesson: when a decorator's strictness doesn't match the logic inside the function, that's a sign one of the two is wrong — either the decorator is too strict (locking out people the body was clearly written to support) or the body's extra checks are unnecessary dead code (if only superusers can ever reach it, checking company_id on every superuser is redundant, since superusers likely span/manage multiple companies anyway).

# Connections

# This file is the "front door" for reading user data — pulling together UserType/UserConnection (file 1), the require_owner decorator (file 8), and three selectors that presumably each call into the models you've built up (User, UserRole, etc.) via straightforward Django ORM queries, following the same query patterns (values_list, select_related) you saw in the permissions selector file.

# What I should remember
# Not every field needs a permission decorator — me is correctly left open, because "see your own data" needs no authorization beyond being logged in at all. Absence of a decorator can be just as intentional as its presence.
# Decorators apply bottom-up, closest-to-the-function first — @require_owner() runs before @strawberry.field registers the result.
# Optional[X] = None parameters build flexible, filterable query endpoints — one field, many possible combinations of filters, without needing separate endpoints for each use case.
# a, b = some_function(...) (tuple unpacking) is a clean way to receive multiple return values in one line, when a function returns a tuple.
# Always sanity-check a decorator's strictness against what the function body actually does — if the body contains scoping/filtering logic that only makes sense for regular users, but the decorator restricts access to superusers only, one of the two is likely a mistake.