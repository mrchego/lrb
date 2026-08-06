from types import SimpleNamespace

def make_info(*, user):
    request = SimpleNamespace(user=user)
    
    return SimpleNamespace(
        context=SimpleNamespace(request=request)
    )
    
    
    
# 1. Purpose (why this exists)

# Strawberry GraphQL resolvers always receive an info object as part of how they're called — and inside that info object, your project stores the current request, and inside that, the currently logged-in user (that's how a resolver knows "who is asking for this data" — think back to require_permission(), which needs to check whose permissions it's checking). When you're writing tests for your services or resolvers, you don't have a real HTTP request coming in — there's no real browser, no real login session. But your resolver code still expects to receive something shaped like a real info object, with .context.request.user reachable on it. This file builds a fake, minimal stand-in for that — just enough structure to satisfy what your resolver code expects to find, without any of the real GraphQL/HTTP machinery actually running.

# 2. The import
# python
# from types import SimpleNamespace

# types is a built-in Python toolbox, and SimpleNamespace is one specific tool from it. Here's the easiest way to think about it: normally, if you want an object where you can do something.user or something.request, you'd have to write a whole class with an __init__ method (like ApplicationError did). SimpleNamespace is a shortcut — it lets you create a bare, simple object with whatever named attributes you want, instantly, without writing a class for it. It exists purely so you can quickly bundle a few named values together into one object.

# 3. The function
# python
# def make_info(*, user):

# One input, user — and notice *, before it, forcing it to be passed by name: make_info(user=some_test_user). Since there's only one parameter here, this isn't about preventing a mix-up between two similar arguments (like we discussed with paginate_queryset) — it's more about clarity at the call site: make_info(user=test_user) reads unambiguously, versus make_info(test_user), which is only slightly less clear. Either reasoning is valid; the practical effect is the same either way.

# python
#     request = SimpleNamespace(user=user)

# Creates a small fake object, and gives it exactly one attribute: .user, holding whatever user was passed in. So now you can do request.user and get back your test user — just like you could on a real Django request object.

# python
#     return SimpleNamespace(
#         context=SimpleNamespace(request=request)
#     )

# Builds and returns the outer fake object — this one has exactly one attribute, .context, which itself is another SimpleNamespace, holding .request (the fake request we just built above).

# Why nested like this? Because it has to match the exact shape your real resolvers expect to navigate: info.context.request.user. This function isn't inventing a new shape — it's mimicking, as minimally as possible, the exact chain of attributes Strawberry's real info object provides, so that a resolver or service being tested can't tell the difference between a real request and this fake one, at least not for the one thing it usually cares about (.user).


# DIY — How to Build Your Own Fake Test Object

# For any future test that needs a "fake version of some real, complex object" (a fake request, a fake response, a fake external API client):

# Identify the exact minimum shape the code under test actually reaches into. Don't try to fully replicate a real Django HttpRequest or a real Strawberry Info object — that's usually huge and mostly irrelevant to what you're testing. Trace through the code being tested and note only the specific attributes it actually accesses (here: just .context.request.user).
# Use SimpleNamespace for quick, throwaway fake objects — it's the fastest way to bundle a few named attributes together without writing a real class, and it's genuinely meant for exactly this kind of lightweight stand-in.
# Nest SimpleNamespaces to mirror the real object's attribute chain exactly — if real code does info.context.request.user, your fake needs that same chain, not a flattened shortcut like info.user, or the real code under test will fail with an AttributeError the moment it tries to walk that path.
# Keep it minimal on purpose — if a test later needs one more attribute (like request.session), add it only when a real test actually needs it — don't pre-build a giant fake object "just in case." A fake that's too thin fails loudly and immediately when something's missing (a good thing — it tells you exactly what your test needs); a fake that's too elaborate becomes its own maintenance burden.