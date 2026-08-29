from functools import wraps
from lrb.core.exceptions import AppPermissionDeniedError
from lrb.authorization.selectors.user_has_permission import user_has_permission

def require_permission(codename):
    def decorator(resolver):
        @wraps(resolver)
        def wrapper(self, info, *args, **kwargs):
            user = info.context.request.user
            if not user.is_authenticated:
                raise AppPermissionDeniedError("Authentication required.")
            if not user_has_permission(user=user, codename=codename):
                raise AppPermissionDeniedError(f"Missing permission: {codename}")
            return resolver(self, info, *args, **kwargs)
        return wrapper
    return decorator

def require_owner():
    def decorator(resolver):
        @wraps(resolver)
        def wrapper(self, info, *args, **kwargs):
            user = info.context.request.user
            if not user.is_authenticated:
                raise AppPermissionDeniedError("Authentication required.")
            if not user.is_superuser:
                raise AppPermissionDeniedError(
                     "Only the company owner can perform this action."
                )
            return resolver(self, info, *args, **kwargs)
        return wrapper
    return decorator


# This file is the payoff for everything you've learned so far — require_permission and require_owner are the actual decorators your project's services and resolvers use. It's also the most advanced piece of syntax yet: a decorator that takes an argument, which means three levels of nested functions. Let's build this up slowly, because this pattern trips up almost everyone the first time.

# Imports
# python
# from functools import wraps
# from lrb.core.exceptions import AppPermissionDeniedError
# from lrb.authorization.selectors.user_has_permission import user_has_permission
# functools.wraps — a helper decorator you'll see used inside this file (explained below).
# AppPermissionDeniedError — a custom exception class from your core app, used instead of a generic Python error, so your GraphQL layer can catch it specifically and turn it into a clean, user-facing error message (rather than crashing).
# user_has_permission — the exact function from your last file.
# Background you need first: functions can return functions

# Before touching require_permission, you need one core idea: in Python, a function is just a value, like a number or string. That means a function can create and return another function. Small example:

# python
# def make_adder(n):
#     def add(x):
#         return x + n
#     return add

# add_five = make_adder(5)
# add_five(10)  # 15

# Notice add "remembers" n even after make_adder has finished running. This remembering is called a closure — the inner function keeps access to variables from the outer function that created it. This is the exact trick require_permission uses, just with three layers instead of two.

# require_permission — three nested layers
# python
# def require_permission(codename):
#     def decorator(resolver):
#         @wraps(resolver)
#         def wrapper(self, info, *args, **kwargs):
#             ...
#         return wrapper
#     return decorator

# Let's name the three layers so we can talk about them clearly:

# Layer 1: require_permission(codename) — the outer function. This is what you call directly, with a permission name, like require_permission("can_edit_orders").
# Layer 2: decorator(resolver) — a function defined inside Layer 1. This is what actually becomes "the decorator" applied to your GraphQL resolver.
# Layer 3: wrapper(self, info, *args, **kwargs) — a function defined inside Layer 2. This is the function that actually replaces your original resolver and runs every time it's called.

# Why three layers? What problem does this solve?

# A normal decorator (like @strawberry.field from way back in your first file) takes no configuration — it's always applied exactly the same way. But require_permission needs an argument — which permission to check — and Python's @ syntax doesn't let a decorator directly accept custom arguments on its own. The trick is to make the "thing with @ in front of it" (decorator) get produced by an outer function (require_permission) that already has codename locked in via closure. So:

# python
# @require_permission("can_edit_orders")
# def update_order(self, info, ...):
#     ...

# Here's what Python actually does, step by step, when it sees this:

# It calls require_permission("can_edit_orders") first — this runs Layer 1's body, which just defines decorator (Layer 2) and returns it. At this point, codename is fixed as "can_edit_orders" inside decorator's closure.
# Whatever came back from step 1 (the decorator function) is now used as the actual decorator, applied to update_order. So Python effectively calls decorator(update_order).
# decorator(update_order) runs Layer 2's body: it defines wrapper (Layer 3), and returns that.
# The name update_order now points to wrapper, not your original function. From now on, whenever GraphQL calls update_order(...), it's really calling wrapper(...).

# This is why @require_permission("can_edit_orders") needs those parentheses even though @strawberry.field (from earlier files) doesn't — require_permission isn't the decorator itself; it's a function that builds and returns the decorator.

# @wraps(resolver) — why it's there
# python
# @wraps(resolver)
# def wrapper(self, info, *args, **kwargs):

# When you replace a function with a wrapper (as decorators always do), Python's default behavior is that the wrapper "loses" the original function's identity — its __name__, its docstring, etc. all end up showing wrapper instead of update_order. This causes confusing bugs and unhelpful debugging/logging (imagine every decorated resolver's errors all saying "in function wrapper" instead of naming the real function). @wraps(resolver) fixes this: it copies resolver's name, docstring, and other metadata onto wrapper, so from the outside, wrapper still looks and behaves like update_order to any tool inspecting it — even though it's really running different code underneath.

# wrapper(self, info, *args, **kwargs) — the signature
# self — since this decorates a method on a GraphQL resolver class (not a standalone function), the wrapped function still needs to accept self as its first parameter, just like any method.
# info — this is a Strawberry-specific parameter every resolver receives, holding contextual information about the current GraphQL request — including, as you'll see, who's making the request.
# *args — a new syntax: the single * (attached to a name this time, unlike the bare * you saw in keyword-only functions) means "collect any extra positional arguments into a tuple called args." This lets wrapper accept resolvers with any number of extra parameters, without needing to know in advance what they are.
# **kwargs — similarly, ** collects any extra keyword arguments into a dictionary called kwargs.

# Why *args, **kwargs here specifically?
# This decorator needs to work on any resolver, regardless of what specific arguments that resolver takes (one resolver might take input: UpdateProfileInput, another might take user_id and duration_minutes directly). Rather than writing a separate decorator for every possible resolver signature, *args, **kwargs says: "whatever arguments come in, just catch them all here, and pass them straight through unchanged to the real resolver." This is the standard, idiomatic way to write a decorator that must work generically across many different functions.

# Body
# python
# user = info.context.request.user
# if not user.is_authenticated:
#     raise AppPermissionDeniedError("Authentication required.")
# if not user_has_permission(user=user, codename=codename):
#     raise AppPermissionDeniedError(f"Missing permission: {codename}")
# return resolver(self, info, *args, **kwargs)
# user = info.context.request.user — digs into info (the request info Strawberry hands every resolver) to find the currently logged-in user. This is . chaining: info has a .context, which has a .request (likely the underlying Django HTTP request), which has a .user (Django's standard way of exposing the logged-in user on a request).
# if not user.is_authenticated: — is_authenticated is a real Django User property: True if someone is logged in, False for an anonymous visitor. If not authenticated, raise AppPermissionDeniedError(...) — this immediately stops execution and throws the error up to whatever calls this resolver (GraphQL will catch it and turn it into an error response to the client).
# if not user_has_permission(user=user, codename=codename): — here's the closure in action: codename isn't a parameter of wrapper at all — it was captured all the way back from Layer 1 (require_permission(codename)), and wrapper still has access to it. This calls the exact function from your previous file.
# raise AppPermissionDeniedError(f"Missing permission: {codename}") — a helpful, specific error message naming exactly which permission was missing.
# return resolver(self, info, *args, **kwargs) — only if both checks pass, finally call the real, original resolver, passing along everything exactly as it was received (self, info, plus whatever extra args/kwargs came in). This is the "gatekeeper" pattern: wrapper runs before the real function, and only lets execution continue to the real logic if all conditions are satisfied.
# require_owner — same skeleton, different check
# python
# def require_owner():
#     def decorator(resolver):
#         @wraps(resolver)
#         def wrapper(self, info, *args, **kwargs):
#             user = info.context.request.user
#             if not user.is_authenticated:
#                 raise AppPermissionDeniedError("Authentication required.")
#             if not user.is_superuser:
#                 raise AppPermissionDeniedError(
#                      "Only the company owner can perform this action."
#                 )
#             return resolver(self, info, *args, **kwargs)
#         return wrapper
#     return decorator

# Notice require_owner() is called with empty parentheses — it takes no arguments (there's no "which permission" to specify; it's a single fixed check: superuser or not). But it still needs all three layers, even with nothing to configure, because @require_owner() (with parentheses) needs a function call to happen first — the outer require_owner() call — before the actual decorator (decorator) is produced. If it were written as a plain two-layer decorator instead (@require_owner, no parentheses, no outer function), it also could have worked structurally — but keeping the same three-layer shape as require_permission makes both decorators consistent and interchangeable-looking at the call site (@require_permission("x") and @require_owner() read the same way), which is a deliberate, worthwhile consistency choice.

# The only logic difference: instead of calling user_has_permission, it directly checks user.is_superuser — matching exactly the short-circuit you saw at the top of user_has_permission itself, but enforced here as an absolute, non-negotiable gate rather than one branch of a broader check.

# Connections — how these get used
# python
# @strawberry.mutation
# @require_permission("can_edit_orders")
# def update_order(self, info, input: UpdateOrderInput) -> OrderMutationPayload:
#     ...

# @strawberry.mutation
# @require_owner()
# def promote_to_owner(self, info, input: PromoteToOwnerInput) -> UserMutationPayload:
#     ...

# This is the enforcement layer sitting directly in front of every sensitive mutation in your schema — including the PromoteToOwnerInput/AdminUpdateUserInput mutations from your second file. When multiple decorators stack like this, they apply bottom-up: require_permission(...) wraps the real resolver first, then @strawberry.mutation wraps that to register it with GraphQL — so the permission check runs before Strawberry even considers it a valid GraphQL call to route through.

# What I should remember
# A decorator that takes an argument needs three nested function layers, not two: outer function (captures the argument), middle function (the real decorator, receives the target function), inner function (the replacement that actually runs).
# Closures let inner functions "remember" variables from outer functions even after the outer function has finished running — this is exactly how codename survives inside wrapper.
# *args, **kwargs let a wrapper accept and forward any arguments unchanged — essential for a generic decorator meant to work on many different functions.
# @wraps(original_function) preserves the original function's name/metadata on the wrapper — always use it when writing a decorator, or debugging/logging becomes confusing.
# The "gatekeeper" pattern: check conditions, raise on failure, only call the real function at the very end — this is the shape of almost every authorization decorator you'll ever read or write.