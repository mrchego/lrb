import strawberry
from lrb.accounts.graphql.inputs import (
    UpdateProfileInput,
    AdminUpdateUserInput,
    UserIdInput,
    LockUserInput,
    BulkUserIdsInput,
    BulkLockUserInput,
    PromoteToOwnerInput,
    DemoteOwnerInput,
)
from lrb.accounts.graphql.payloads import UserMutationPayload
from lrb.core.graphql.payloads import (
    BulkActionPayload,
    to_bulk_payload,
    SimpleMutationPayload,
)
from lrb.accounts.selectors.get_current_user_or_raise import get_current_user_or_raise
from lrb.accounts.selectors.get_current_user import get_current_user
from lrb.accounts.services.update_user import update_user
from lrb.accounts.services.activate_user import activate_user
from lrb.accounts.services.deactivate_user import deactivate_user
from lrb.accounts.services.delete_user import delete_user
from lrb.accounts.services.lock_user import lock_user
from lrb.accounts.services.unlock_user import unlock_user
from lrb.accounts.services.force_password_reset import force_password_reset
from lrb.accounts.services.bulk_activate_users import bulk_activate_users
from lrb.accounts.services.bulk_deactivate_users import bulk_deactivate_users
from lrb.accounts.services.bulk_delete_users import bulk_delete_users
from lrb.accounts.services.bulk_lock_users import bulk_lock_users
from lrb.accounts.services.bulk_unlock_users import bulk_unlock_users
from lrb.accounts.services.bulk_force_password_reset import bulk_force_password_reset
from lrb.accounts.services.restore_user import restore_user
from lrb.accounts.services.bulk_restore_users import bulk_restore_users
from lrb.accounts.services.promote_to_owner import promote_to_owner
from lrb.accounts.services.demote_owner import demote_owner
from lrb.authorization.decorators import require_owner
from lrb.core.exceptions import ApplicationError, AppPermissionDeniedError
from lrb.core.graphql.errors import format_application_error


@strawberry.type
class UserMutation:
    @strawberry.mutation
    def update_profile(
        self, info: strawberry.Info, input: UpdateProfileInput
    ) -> UserMutationPayload:
        current = get_current_user_or_raise(info)
        try:
            kwargs = {
                k: v
                for k, v in {
                    "first_name": input.first_name,
                    "last_name": input.last_name,
                    "phone": input.phone,
                    "avatar": input.avatar,
                }.items()
                if v is not None
            }
            user = update_user(user_id=current.id, **kwargs)
            return UserMutationPayload(success=True, user=user)
        except ApplicationError as e:
            return UserMutationPayload(
                success=False, errors=[format_application_error(e)]
            )

    @strawberry.mutation
    @require_owner()
    def admin_update_user(
        self, info: strawberry.Info, input: AdminUpdateUserInput
    ) -> UserMutationPayload:
        current = get_current_user_or_raise(info)
        try:
            kwargs = {
                k: v
                for k, v in {
                    "first_name": input.first_name,
                    "last_name": input.last_name,
                    "phone": input.phone,
                    "avatar": input.avatar,
                }.items()
                if v is not None
            }
            user = update_user(user_id=input.user_id, **kwargs)
            return UserMutationPayload(success=True, user=user)
        except ApplicationError as e:
            return UserMutationPayload(
                success=False, errors=[format_application_error(e)]
            )

    @strawberry.mutation
    @require_owner()
    def activate_user(
        self, info: strawberry.Info, input: UserIdInput
    ) -> SimpleMutationPayload:
        current = get_current_user_or_raise(info)
        try:
            activate_user(user_id=input.user_id)
            return SimpleMutationPayload(success=True)
        except ApplicationError as e:
            return SimpleMutationPayload(
                success=False, errors=[format_application_error(e)]
            )

    @strawberry.mutation
    @require_owner()
    def deactivate_user(
        self, info: strawberry.Info, input: UserIdInput
    ) -> SimpleMutationPayload:
        current = get_current_user_or_raise(info)
        try:
            deactivate_user(user_id=input.user_id)
            return SimpleMutationPayload(success=True)
        except ApplicationError as e:
            return SimpleMutationPayload(
                success=False, errors=[format_application_error(e)]
            )

    @strawberry.mutation
    @require_owner()
    def delete_user(
        self, info: strawberry.Info, input: UserIdInput
    ) -> SimpleMutationPayload:
        current = get_current_user_or_raise(info)
        try:
            delete_user(user_id=input.user_id)
            return SimpleMutationPayload(success=True)
        except ApplicationError as e:
            return SimpleMutationPayload(
                success=False, errors=[format_application_error(e)]
            )

    @strawberry.mutation
    @require_owner()
    def lock_user(
        self, info: strawberry.Info, input: LockUserInput
    ) -> SimpleMutationPayload:
        current = get_current_user_or_raise(info)
        try:
            lock_user(user_id=input.user_id, duration_minutes=input.duration_minutes)
            return SimpleMutationPayload(success=True)
        except ApplicationError as e:
            return SimpleMutationPayload(
                success=False, errors=[format_application_error(e)]
            )

    @strawberry.mutation
    @require_owner()
    def unlock_user(
        self, info: strawberry.Info, input: UserIdInput
    ) -> SimpleMutationPayload:
        current = get_current_user_or_raise(info)
        try:
            unlock_user(user_id=input.user_id)
            return SimpleMutationPayload(success=True)
        except ApplicationError as e:
            return SimpleMutationPayload(
                success=False, errors=[format_application_error(e)]
            )

    @strawberry.mutation
    @require_owner()
    def force_password_reset(
        self, info: strawberry.Info, input: UserIdInput
    ) -> SimpleMutationPayload:
        current = get_current_user_or_raise(info)
        try:
            force_password_reset(user_id=input.user_id)
            return SimpleMutationPayload(success=True)
        except ApplicationError as e:
            return SimpleMutationPayload(
                success=False, errors=[format_application_error(e)]
            )

    @strawberry.mutation
    @require_owner()
    def bulk_activate_users(
        self, info: strawberry.Info, input: BulkUserIdsInput
    ) -> BulkActionPayload:
        current = get_current_user_or_raise(info)
        result = bulk_activate_users(
            user_ids=input.user_ids,
            company_id=str(current.company_id),
            current_user_id=current.id,
        )
        return to_bulk_payload(result)

    @strawberry.mutation
    @require_owner()
    def bulk_delete_users(
        self, info: strawberry.Info, input: BulkUserIdsInput
    ) -> BulkActionPayload:
        current = get_current_user_or_raise(info)
        result = bulk_delete_users(
            user_ids=input.user_ids,
            company_id=str(current.company_id),
            current_user_id=current.id,
        )
        return to_bulk_payload(result)

    @strawberry.mutation
    @require_owner()
    def bulk_lock_users(
        self, info: strawberry.Info, input: BulkLockUserInput
    ) -> BulkActionPayload:
        current = get_current_user_or_raise(info)
        result = bulk_lock_users(
            user_ids=input.user_ids,
            company_id=str(current.company_id),
            current_user_id=current.id,
            duration_minutes=input.duration_minutes,
        )
        return to_bulk_payload(result)

    @strawberry.mutation
    @require_owner()
    def bulk_unlock_users(
        self, info: strawberry.Info, input: BulkUserIdsInput
    ) -> BulkActionPayload:
        current = get_current_user_or_raise(info)
        result = bulk_unlock_users(
            user_ids=input.user_ids,
            company_id=str(current.company_id),
            current_user_id=current.id,
        )
        return to_bulk_payload(result)

    @strawberry.mutation
    @require_owner()
    def bulk_force_password_reset(
        self, info: strawberry.Info, input: BulkUserIdsInput
    ) -> BulkActionPayload:
        current = get_current_user_or_raise(info)
        result = bulk_force_password_reset(
            user_ids=input.user_ids,
            company_id=str(current.company_id),
            current_user_id=current.id,
        )
        return to_bulk_payload(result)

    @strawberry.mutation
    @require_owner()
    def restore_user(
        self, info: strawberry.Info, input: UserIdInput
    ) -> SimpleMutationPayload:
        current = get_current_user_or_raise(info)
        try:
            restore_user(user_id=input.user_id)
            return SimpleMutationPayload(success=True)
        except ApplicationError as e:
            return SimpleMutationPayload(
                success=False, errors=[format_application_error(e)]
            )

    @strawberry.mutation
    @require_owner()
    def bulk_restore_users(
        self, info: strawberry.Info, input: BulkUserIdsInput
    ) -> BulkActionPayload:
        current = get_current_user_or_raise(info)
        result = bulk_restore_users(
            user_ids=input.user_ids,
            company_id=str(current.company_id),
        )
        return to_bulk_payload(result)

    @strawberry.mutation
    @require_owner()
    def promote_to_owner(
        self, info: strawberry.Info, input: PromoteToOwnerInput
    ) -> SimpleMutationPayload:
        current = get_current_user_or_raise(info)
        try:
            promote_to_owner(
                user_id=input.user_id,
            )
            return SimpleMutationPayload(success=True)
        except ApplicationError as e:
            return SimpleMutationPayload(
                success=False, errors=[format_application_error(e)]
            )

    @strawberry.mutation
    @require_owner()
    def demote_owner(
        self, info: strawberry.Info, input: DemoteOwnerInput
    ) -> SimpleMutationPayload:
        current = get_current_user_or_raise(info)
        try:
            demote_owner(user_id=input.user_id, company_id=str(current.company_id))
            return SimpleMutationPayload(success=True)
        except ApplicationError as e:
            return SimpleMutationPayload(
                success=False, errors=[format_application_error(e)]
            )



# Teaching: UserMutation (GraphQL Mutation Class)

# This is a bigger file, but it's built almost entirely from one repeated pattern, copied ~19 times with small variations. So I'll teach the pattern deeply once, then speed through the repeats — exactly like your reading rule says.

# 1. What is it?

# This defines a GraphQL mutation class — a collection of "write" operations (update, delete, lock, promote, etc.) that a frontend can call to change data about users. Each method inside is one mutation, like one API endpoint.

# New pieces we haven't covered before (beyond last time's get_current_user_or_raise):

# @strawberry.type — a class decorator
# @strawberry.mutation — a method decorator
# @require_owner() — another decorator, from your own project
# class UserMutation: — class definition
# self — the first parameter of every method
# try / except ApplicationError as e: — error handling
# dict comprehension: {k: v for k, v in {...}.items() if v is not None}
# **kwargs — dictionary unpacking into keyword arguments
# str(current.company_id) — type conversion
# 2. How is it written? (new symbols)

# @ (decorator symbol)
# A decorator sits directly above a function or class, with no blank line between them. It means: "take the thing defined right below me, and pass it through this other function first, to wrap or register it with extra behavior." You don't call the decorator yourself — Python does it automatically the moment it reads the def below.

# @strawberry.type — tells Strawberry "treat this whole class as a GraphQL type" (specifically, a Mutation type — the class name UserMutation and its placement in your root schema is what makes Strawberry know it's the mutation type).
# @strawberry.mutation — tells Strawberry "register this one method as a callable GraphQL mutation" (as opposed to a query, which would use @strawberry.field or @strawberry.mutation isn't used for queries).
# @require_owner() — your own project's decorator, imported from lrb.authorization.decorators. It wraps the method so that before the method's body ever runs, it checks that the caller has "owner" permission. Notice the () after it — require_owner is actually a function that, when called, produces the real decorator. This is called a "decorator factory" (more in section 7).

# Stacking order matters: decorators apply bottom-up, closest-to-the-function first. So for:

# python
# @strawberry.mutation
# @require_owner()
# def admin_update_user(...):

# Python first wraps admin_update_user with require_owner()'s check, then wraps that whole thing with strawberry.mutation's registration. Practically: the permission check happens, and then Strawberry exposes the (already-protected) function to the schema.

# self
# Every method inside a class takes self as its first parameter. It refers to "the specific object this method is being called on." You never pass it manually — Python fills it in automatically when you call a method on an instance. Here, UserMutation doesn't really use any per-instance data (no self.something), so self is present purely because Strawberry requires normal Python method syntax — it's a formality, not something the code relies on.

# try / except SomeError as e:

# try: — "run this block; if any error happens inside it, don't crash — jump down to except instead."
# except ApplicationError as e: — "if the error that happened is an ApplicationError (or a subclass of it), catch it, and give it the temporary name e so I can use it below." Errors not of this type still crash normally — this only catches the specific type named.

# Dict comprehension

# python
# kwargs = {
#     k: v
#     for k, v in {
#         "first_name": input.first_name,
#         "last_name": input.last_name,
#         "phone": input.phone,
#         "avatar": input.avatar,
#     }.items()
#     if v is not None
# }

# Read this right side first:

# {"first_name": ..., ...} — build a plain dictionary from the input fields.
# .items() — turn that dict into pairs you can loop over: ("first_name", value), ("last_name", value), etc.
# for k, v in ...items() — loop through those pairs, calling the key k and the value v each time.
# if v is not None — filter: only keep the pair if the value isn't None.
# k: v at the very front — for every pair that survives the filter, put it into a new dictionary as key: value.

# So the whole expression means: "build a new dictionary containing only the input fields the user actually provided (skip anything left as None/not sent)."

# **kwargs

# python
# user = update_user(user_id=current.id, **kwargs)

# ** in front of a dictionary when calling a function means "unpack this dictionary into separate key=value keyword arguments." If kwargs is {"first_name": "Amina", "phone": "0700..."}, then **kwargs here is exactly the same as writing first_name="Amina", phone="0700..." directly. This is how the code hands a variable number of fields to update_user without knowing in advance which ones were provided — matches your project's rule that service functions take keyword-only arguments.

# str(current.company_id)
# str(...) is a built-in function that converts its input into a text string. company_id is likely a UUID or integer field; converting it to str before passing it into a service is a defensive/explicit choice — the receiving service probably expects a plain string, not a UUID object.

# 3. Signature — one representative example, broken down
# python
# def update_profile(
#     self, info: strawberry.Info, input: UpdateProfileInput
# ) -> UserMutationPayload:
# Piece	Meaning
# def update_profile(	defining a method named update_profile
# self,	required first parameter for any method — "the instance this is called on"
# info: strawberry.Info,	Strawberry auto-supplies this — carries request/session context
# input: UpdateProfileInput	the GraphQL arguments the frontend sent, already validated and shaped into this custom type
# )	end of parameter list
# -> UserMutationPayload:	promises this method returns a UserMutationPayload object — a standard shape (success flag + data or errors) so the frontend always knows what to expect back

# Every mutation in this file follows this exact shape: self, info, input in, some *Payload type out. Once you've read one signature, you've read all 19.

# 4. Class — from scratch
# python
# @strawberry.type
# class UserMutation:

# Why a class here instead of loose functions? Strawberry needs a way to group many mutations under one GraphQL "Mutation" type in the schema (like a folder holding all the "write" operations). A class is Python's natural container for "a bunch of related methods that belong together." You're not creating multiple instances of UserMutation with different data (like you might with a User class representing different people) — this class exists once, purely as an organizational container that Strawberry turns into schema structure. That's why self is never actually used inside any method body.

# 5. Body — walking through update_profile (the fullest example)
# python
# current = get_current_user_or_raise(info)

# Runs the gatekeeper function from your last file — this line either gets a valid, company-attached user, or the function raises AppPermissionDeniedError and everything below never runs.

# python
# try:
#     kwargs = { ... dict comprehension ... }
#     user = update_user(user_id=current.id, **kwargs)
#     return UserMutationPayload(success=True, user=user)
# except ApplicationError as e:
#     return UserMutationPayload(
#         success=False, errors=[format_application_error(e)]
#     )
# Build kwargs from only the fields the user actually sent.
# Call the service update_user, passing current.id (whose profile — from the authenticated session, not user input, so nobody can edit someone else's profile by faking an ID) plus the filtered fields.
# If it works, wrap the updated user in a success payload.
# If the service raises any ApplicationError (a business-rule failure — like "phone number invalid"), catch it, format it into an error message, and return a failure payload instead of crashing the whole request.

# This is the "thin orchestration layer" your project's architecture calls for: no business logic here, just "check who's asking → call the service → shape the result."

# Now the repeated pattern, sped through

# Every other method follows this shape with tiny changes:

# python
# @strawberry.mutation
# @require_owner()
# def X(self, info, input) -> Payload:
#     current = get_current_user_or_raise(info)
#     try:
#         SOME_SERVICE(some_id=input.user_id, ...)
#         return SimpleMutationPayload(success=True)
#     except ApplicationError as e:
#         return SimpleMutationPayload(success=False, errors=[...])
# admin_update_user — same as update_profile, but edits input.user_id (an admin editing someone else) instead of current.id, and is protected by @require_owner() since normal users shouldn't edit other people.
# activate_user, deactivate_user, delete_user, unlock_user, force_password_reset, restore_user — identical shape: call one service with user_id=input.user_id, wrap result in SimpleMutationPayload.
# lock_user — same, but passes an extra field: duration_minutes=input.duration_minutes.

# One thing worth noticing: in these methods, current is assigned but its value is never used again in the body. That's not wasted code — the call itself (get_current_user_or_raise(info)) is what matters, because it performs the check-and-raise side effect. The returned user object just happens not to be needed afterward. This is a common, valid pattern: you call a function for its side effect (the check), not for its return value.

# The bulk mutations (bulk_activate_users, bulk_delete_users, bulk_lock_users, bulk_unlock_users, bulk_force_password_reset) share a different sub-pattern:

# python
# current = get_current_user_or_raise(info)
# result = bulk_activate_users(
#     user_ids=input.user_ids,
#     company_id=str(current.company_id),
#     current_user_id=current.id,
# )
# return to_bulk_payload(result)

# Here current is used — its company_id and id are passed into the service, so bulk actions stay scoped to the caller's own company and can record who performed the action. Notice: no try/except here. That's a real inconsistency worth flagging (see section 11, Common Mistakes) — either these services never raise ApplicationError, or errors here would crash instead of returning a graceful payload, unlike the rest of the file.

# promote_to_owner and demote_owner go back to the try/except + SimpleMutationPayload shape, with demote_owner additionally passing company_id=str(current.company_id).

# 6. Why?

# Why does almost every mutation call get_current_user_or_raise(info) even though @require_owner() is already checking permissions?
# These are two different questions: "is anyone logged in at all?" (authentication) vs. "does this logged-in person have owner-level permission?" (authorization). @require_owner() likely still needs to know who the current user is internally to check their permissions — but this method body also needs current itself (for current.id, current.company_id) to actually perform the action. So both are doing necessary, distinct work.

# Why return a "payload" object instead of just raising errors up to Strawberry directly for everything?
# Two different error strategies are intentionally mixed here:

# get_current_user_or_raise raising AppPermissionDeniedError → this is meant to bubble all the way up and become a hard GraphQL error (you're not logged in — nothing to gracefully recover from).
# ApplicationError caught locally and turned into success=False, errors=[...] → this is a business validation failure (like "that phone number's already taken"), which the frontend wants to show inline on a form, not as a scary crash. Returning a normal payload with success: False lets the GraphQL response still be "successful" at the protocol level, just carrying a failure result.

# Why the dict-comprehension-with-filter for update fields (kwargs)?
# GraphQL input types (UpdateProfileInput) typically make every field optional, defaulting to None if the client didn't send it. If the code just always passed all four fields to update_user, an unsent field would come through as None and might overwrite existing data with nothing. Filtering out None values means "only touch the fields the client actually intended to change" — a common pattern for partial updates (PATCH-style, not full overwrite).

# 7. Connections

# Imports at the top show the layering your architecture doc describes:

# graphql/inputs and graphql/payloads — the shapes of data going in and out of the API boundary.
# selectors/get_current_user* — read-only lookups.
# services/* — where all real business logic and database writes happen (this file never touches the database directly).
# authorization/decorators — cross-cutting permission checks, reused across many mutation classes, not just this one.
# core/exceptions and core/graphql/errors — shared, project-wide error types and formatting, so every app in your project (accounts, orders, staff...) reports errors the same way.

# What comes in: info (session/request context) and input (validated GraphQL arguments) for every method.
# What goes out: always one of your project's standard payload types (UserMutationPayload, SimpleMutationPayload, BulkActionPayload) — never a raw User object or a raw dict. This consistency is what lets your frontend write one predictable pattern for handling any mutation response.

# This file sits between your GraphQL schema (which exposes it to the frontend) and your services/ layer (which does the actual work) — exactly the "thin orchestration" role your project's conventions describe.

# 8. Advanced concepts

# A) Decorator factories — @require_owner() vs @require_owner
# Notice the parentheses. A plain decorator, @require_owner, would mean "here's a ready-made wrapper function, apply it directly." But @require_owner() means: "call require_owner() first (with no arguments), and whatever function that call returns is the actual decorator to apply." This pattern — a function that returns a decorator — is used when a decorator needs configuration. Even though no arguments are passed here, keeping the () keeps it consistent with sibling decorators in your project that do take arguments, like require_permission(codename) (mentioned in your project conventions) — same factory pattern, this one just needs no config.

# B) Decorator stacking order

# python
# @strawberry.mutation
# @require_owner()
# def admin_update_user(...):

# Reading top-to-bottom you might think strawberry.mutation runs first — it doesn't. Decorators apply bottom-up: Python first wraps the raw function with require_owner(), producing a new "permission-checked" function, and then wraps that whole thing with strawberry.mutation. So the call order when someone actually invokes it is: Strawberry receives the call → hands off to the require_owner-wrapped version → which checks permission → then, if it passes, calls your real admin_update_user body.

# C) Filtering with a comprehension instead of a loop
# The dict comprehension does in one expression what a for loop + if + .append()/assignment would take four lines to do. It's not just shorter — comprehensions are considered more "Pythonic" (idiomatic) for building a new collection from an existing one, and they're common enough that recognizing the shape instantly ({... for ... in ... if ...}) is a core reading skill.

# D) **kwargs connects directly to your project's "keyword-only arguments" convention
# Since your services are written to only accept keyword arguments (def update_user(*, user_id, first_name=None, ...) presumably), **kwargs is the only clean way to forward a variable, filtered set of fields into them — you can't build that call with plain positional arguments.

# 9. Small example

# A miniature version of the update_profile shape, no GraphQL:

# python
# class Errors(Exception): pass

# def update_user(*, user_id, **fields):
#     print(f"Updating user {user_id} with {fields}")
#     return {"id": user_id, **fields}

# def update_profile_demo(current_id, raw_input):
#     kwargs = {k: v for k, v in raw_input.items() if v is not None}
#     try:
#         user = update_user(user_id=current_id, **kwargs)
#         return {"success": True, "user": user}
#     except Errors as e:
#         return {"success": False, "errors": [str(e)]}

# result = update_profile_demo(7, {"first_name": "Amina", "phone": None})
# # Updating user 7 with {'first_name': 'Amina'}
# # result = {'success': True, 'user': {'id': 7, 'first_name': 'Amina'}}

# phone: None never reached the service — exactly the filtering behavior from the real file.

# 10. What you should remember
# A decorator with () after it (@require_owner()) is a factory — it builds the real decorator when Python reads the file. A decorator without () is used directly as-is. Watch for this distinction.
# current = get_current_user_or_raise(info) can be a pure side-effect call. Not every assigned variable needs to be used later — sometimes the act of calling is the whole point (the auth check), even if the returned value goes unused. Don't assume unused variables are mistakes.
# {k: v for k, v in d.items() if v is not None} is the standard "keep only the fields that were actually provided" pattern — recognize this shape whenever you see partial/PATCH-style updates.
# **kwargs at a call site unpacks a dict into keyword arguments — it exists specifically to forward a variable set of fields into a function that only accepts keyword arguments, matching your project's service-layer convention.
# Success/failure should be a return value (a payload), not always an exception — reserve raising for things the caller truly can't recover from (like "you're not even logged in"); catch expected business failures locally and turn them into a normal, structured response instead.

# One inconsistency worth flagging (matches the "actively catch drift" instinct you mentioned): the five bulk-action mutations (bulk_activate_users, bulk_delete_users, bulk_lock_users, bulk_unlock_users, bulk_force_password_reset) skip the try/except ApplicationError wrapping that every single-user mutation uses. Either that's deliberate (maybe those services never raise ApplicationError, or to_bulk_payload already handles per-item failures internally), or it's a gap where a business-rule failure would crash the whole bulk request instead of returning a clean success: False payload like its siblings do. Worth checking the bulk_* service implementations to see which it is.