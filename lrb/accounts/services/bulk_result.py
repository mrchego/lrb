from dataclasses import dataclass, field

@dataclass
class BulkActionResult:
    succeeded: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    
    def add_success(self, * ,user_id:str) -> None:
        self.succeeded.append(user_id)
        
    def add_failure(self, * ,user_id:str, reason:str) -> None:
        self.failed.append({"user_id": user_id, "reason": reason})
        
        
# 1. Purpose — Why this exists

# What problem is this solving?
# Every single-user function you've built (activate_user, demote_owner, deactivate_user) handles exactly one user and either returns them or raises. But a real admin tool often needs bulk actions — "deactivate these 50 users" — where some might succeed and some might fail (already deactivated, is the last owner, doesn't exist), and the caller needs to know which succeeded and which failed, and why each failure happened. BulkActionResult is a container purpose-built to accumulate exactly that information as a bulk operation works through its list.

# Why not just use two plain lists directly in whatever function runs the bulk action?
# You could — succeeded = [] and failed = [] as local variables. But bundling them into one named object gives you a single thing to pass around, return, and extend later (add a skipped category, add a total_processed count) without changing every function's signature. It also gives you a natural place to hang small helper methods (add_success, add_failure) that keep the shape of what gets recorded consistent, rather than every calling function constructing dictionaries by hand and risking inconsistent keys.

# When is this used?
# Inside a bulk operation — something like bulk_deactivate_users(user_ids=[...]) — looping over IDs, calling deactivate_user for each, and recording the outcome into one BulkActionResult to return at the end.

# What breaks without it?
# Each bulk operation would invent its own ad-hoc way of tracking successes/failures — maybe a dict here, a list of tuples there — making every caller handle a slightly different shape, and every failure report potentially missing the reason.

# 2. Imports — explained like you've never programmed
# python
# from dataclasses import dataclass, field

# dataclasses is a module built into Python itself (nothing to install) — it exists specifically to remove repetitive boilerplate when you write classes whose main job is holding data. dataclass and field are two separate tools pulled from it in one line, exactly like transaction, IntegrityError from django.db earlier.

# dataclass — this is what you'll see used as a decorator (the @ syntax) directly above the class definition. It automatically generates code you'd otherwise have to write by hand — most importantly, an __init__ method (the thing that runs when you create a new instance) that sets up each field, based purely on the class body you write.
# field — a helper used inside a dataclass to customize exactly how one specific attribute gets initialized, when the simple "just give it a default value" isn't enough (which is exactly the situation here — more in a moment).
# 3. Signature — every symbol explained
# python
# @dataclass
# class BulkActionResult:

# @dataclass — the decorator from the import. Placing it directly above class BulkActionResult: tells Python: "generate the usual class machinery (especially __init__) automatically, based on the attributes I declare in the body below." Without this decorator, you'd have to write __init__(self, succeeded=None, failed=None): ... by hand, manually assigning each parameter to self.

# class BulkActionResult: — class is the keyword that begins a class definition, the same way def begins a function definition. BulkActionResult is the name — by convention, class names in Python use CapitalizedWords (this is why User, Company are capitalized, but get_user, create_user are lowercase — a strong, consistent naming signal throughout Python that "capitalized = a class/type," "lowercase = a function/variable").

# python
#     succeeded: list[str] = field(default_factory=list)
#     failed: list[str] = field(default_factory=list)

# These two lines, inside the class body but not inside any method, are class-level attribute declarations — this is the dataclass-specific syntax that tells @dataclass "every instance of this class should have an attribute called succeeded, type-hinted as list[str], and here's how to give it its starting value."

# Why field(default_factory=list) instead of just = []?
# This is a genuinely important, non-obvious Python trap, worth explaining fully rather than glossing over. If you wrote succeeded: list[str] = [] directly, that single empty list would be created once, when the class itself is defined — and then every single instance of BulkActionResult you ever create would silently share that same list object. Appending to one instance's succeeded list would show up in every other instance's succeeded list too, because they'd all be pointing at the identical list in memory. field(default_factory=list) tells the dataclass machinery instead: "don't share one default — call list() fresh, once per new instance, to build each one its own independent empty list." default_factory takes a function (here, the built-in list itself, referenced without parentheses — we're not calling it now, we're handing over "here's the function to call later, once per instance") and calls it each time a new object needs its default.

# No explicit __init__ anywhere in this file — and that's the entire point of @dataclass. Because you declared succeeded and failed as typed class attributes, @dataclass automatically generates an __init__ equivalent to:

# python
# def __init__(self, succeeded=None, failed=None):
#     self.succeeded = succeeded if succeeded is not None else []
#     self.failed = failed if failed is not None else []

# (roughly — the actual generated code handles the default_factory mechanism precisely, avoiding the shared-list trap explained above). You never see this code because @dataclass writes it for you, but it's genuinely running whenever you write BulkActionResult().

# 4. Classes — from scratch, since this is genuinely the first one

# Why use a class here instead of two plain functions?
# Go back to the test we've used every single time we said "no class needed" in earlier files: does this need to bundle data together with behavior that acts on that data, persisting across multiple calls? Here, finally, the answer is yes. A bulk operation needs one thing that holds both lists and offers a controlled way to add to them, and that same one thing gets handed around, added to repeatedly across many loop iterations, and eventually returned as a whole — that's a fundamentally different shape than every get_/create_/update_ function you've seen, which each take input, do one thing, and hand back a result without remembering anything.

# What does class actually create?
# Writing class BulkActionResult: doesn't create any actual data yet — it creates a blueprint, a template describing what any BulkActionResult will look like and be able to do. Nothing exists in memory representing "a" bulk action result until you actually write BulkActionResult() somewhere and use it.

# What is an object? What is an instance?
# When you write result = BulkActionResult(), Python uses the blueprint to build one real, concrete thing in memory — that's an instance (a specific realization of the blueprint) — and result is a variable pointing at it. Object and instance are used near-interchangeably in Python — "object" is the more general term (everything in Python is technically an object — even a plain integer), "instance" specifically emphasizes "this is one particular realization of that class's blueprint." If you created a second one, another_result = BulkActionResult(), you'd have two completely separate instances, each with their own independent succeeded/failed lists (this is exactly why the default_factory trap mattered above — without it, those two instances would accidentally share one list).

# Why is self needed?
# Look at the method definitions:

# python
# def add_success(self, *, user_id: str) -> None:
#     self.succeeded.append(user_id)

# self is the first parameter of every method defined inside a class, and it represents "whichever specific instance this method was called on." When you write result.add_success(user_id="abc"), Python automatically passes result itself in as self — you never type it yourself at the call site, but it's genuinely the first argument the method receives internally. Without self, add_success would have no way to know which instance's succeeded list to append to — there could be many BulkActionResult instances alive at once, each needing its own separate list modified, and self is exactly the mechanism that says "modify this one, not any other."

# Concretely, self.succeeded means: "go to the specific instance this method is currently running on, and access its own succeeded attribute" — the exact same dot-access pattern you've used throughout this whole series (request.user, user.is_active), just now happening inside the class that owns the attribute, rather than from outside it.

# 5. Body — line by line
# python
# def add_success(self, *, user_id: str) -> None:
#     self.succeeded.append(user_id=user_id)

# Signature: self first (as explained above, automatic, never passed explicitly by the caller), then * enforcing keyword-only for everything after it — consistent with your project's convention, applied here even inside a class method. user_id: str — the ID to record as successful. -> None — this method doesn't hand back a useful value; its entire job is a side effect (mutating self.succeeded), the same shape as assert_not_last_owner's -> None.

# 🚩 The bug: self.succeeded.append(user_id=user_id).

# .append() is a built-in method every Python list has, and its job is simple: "add exactly one item to the end of this list." But .append() takes its item positionally — it does not accept, and has never accepted, a keyword argument. Writing some_list.append(user_id=user_id) will raise:

# TypeError: list.append() takes no keyword arguments

# immediately, every single time this method is called. This is a real, guaranteed crash — not a subtle edge case like some of the earlier bugs, but one that fires on the very first successful use.

# Why did this happen? It's an understandable slip given everything else in this exact function is keyword-only by convention — the habit of "arguments get names" from your project's own service-layer functions bled into a call to a built-in Python method that simply doesn't work that way. .append() isn't one of your project's functions; it's a fixed part of Python's list type, with its own fixed calling rules that your project's conventions don't (and can't) override.

# Fix:

# python
# self.succeeded.append(user_id)
# python
# def add_failure(self, user_id: str, reason: str) -> None:
#     self.failed.append({"user_id": user_id, "reason": reason})

# Signature: self first, then user_id: str and reason: str — no * here, meaning these are positional, unlike add_success right above it. This is the consistency issue worth flagging directly: two methods on the same class, right next to each other, use two different calling conventions. Given your project's stated, deliberate convention of keyword-only arguments throughout the service layer, add_failure should almost certainly match:

# python
# def add_failure(self, *, user_id: str, reason: str) -> None:

# Body — this one is written correctly: .append({"user_id": user_id, "reason": reason}) — passes a single dictionary as the one positional argument .append() actually expects. Read right to left inside the braces: build a new dict with two key-value pairs, "user_id" mapped to the user_id parameter's value, "reason" mapped to the reason parameter's value — then append that whole dict, as one item, onto self.failed.

# Whole method, plain English: "Record a failure by appending a small dictionary — recording both which user failed and why — onto this instance's failure list."

# 6. Beginner questions, answered proactively

# Why does add_success just append a plain string, while add_failure appends a whole dictionary?
# Because they need to carry different amounts of information. A success needs nothing beyond "which ID succeeded" — matching the type hint succeeded: list[str], a flat list of ID strings. A failure needs both "which ID" and "why," which a single string can't hold cleanly — a dictionary lets you attach a named reason alongside the ID, ready to be shown in a UI ("User X failed: last active owner").

# Why not make failed a list of a proper class too, instead of a bare dictionary?
# You could — a small dataclass like @dataclass class FailedAction: user_id: str; reason: str would give you the same type-safety and autocomplete benefits BulkActionResult itself gets from being a dataclass. Using a plain dict works and is simpler, but loses that structure — a caller has to remember the exact key spellings ("user_id", "reason") rather than getting autocomplete on .user_id/.reason. A reasonable design choice either way; worth knowing it's a choice, not the only option.

# What does -> None actually mean here, and why bother writing it for a method that clearly doesn't return anything obvious?
# Same reasoning as everywhere else you've seen it — it's an explicit promise for readers and tooling: "calling this method is purely for its side effect; don't try to use its return value for anything," distinct from a method someone might otherwise assume hands back the updated list or a success flag.

# 7. Design discussion

# Why give this its own small, dedicated class instead of returning a plain tuple (succeeded_list, failed_list) — similar to how paginate_queryset returns (items, total_count)?
# Worth contrasting these two designs directly, since you've now seen both. paginate_queryset returns exactly two related values with an obvious, fixed, unlikely-to-change shape — a tuple was a reasonable, lightweight choice there. BulkActionResult is doing something with more room to grow — it already has two named helper methods, and it's easy to imagine adding a skipped category, a total_count property, or a to_dict() method for a GraphQL response later. Once a piece of data needs its own behavior (methods) rather than just being read, a class earns its place over a tuple.

# Trade-off worth naming for the add_success/add_failure inconsistency: beyond the immediate .append() bug, the missing * on add_failure means these two methods, despite living on the same class and serving the same conceptual purpose, currently have to be called two different ways — add_success(user_id="x") but add_failure("x", "reason") — which is exactly the kind of small inconsistency that becomes a real source of confusion once a caller (or their editor's autocomplete) doesn't remember which method needs keywords and which doesn't.

# 8. DIY Recipe — build one like this yourself
# Reach for @dataclass when you need a class whose primary job is holding a handful of related pieces of data, without wanting to hand-write __init__ yourself.
# Always use field(default_factory=list) (or dict, set, etc.) for mutable default values — never = [] or = {} directly on a dataclass field — to avoid every instance silently sharing the same underlying list/dict.
# Give the class small, named methods for each way its data gets modified (add_success, add_failure), rather than letting callers reach in and mutate .succeeded/.failed directly — this keeps the shape of what gets stored consistent no matter who's calling it.
# Apply your project's calling conventions (like keyword-only arguments) consistently across every method on the class, not just some of them.
# Double-check the calling convention of any built-in method you use inside your own methods (.append(), .count(), etc.) — your project's own conventions don't change how Python's built-in types work.
# 9. General pattern recognition

# This is the "accumulator object" pattern — new relative to everything else in this project so far:

# python
# @dataclass
# class <Thing>Result:
#     <category_a>: list[...] = field(default_factory=list)
#     <category_b>: list[...] = field(default_factory=list)

#     def add_<category_a>(self, *, ...) -> None:
#         self.<category_a>.append(...)

#     def add_<category_b>(self, *, ...) -> None:
#         self.<category_b>.append(...)

# You'll reach for this shape anywhere you're processing a batch of things and need to track per-item outcomes as you go, rather than an all-or-nothing single result.

# 10. Real project usage

# Exactly where you'd expect, based on everything else you've built:

# python
# def bulk_deactivate_users(*, user_ids: list[str]) -> BulkActionResult:
#     result = BulkActionResult()
#     for user_id in user_ids:
#         try:
#             deactivate_user(user_id=user_id)
#             result.add_success(user_id=user_id)
#         except ApplicationError as e:
#             result.add_failure(user_id=user_id, reason=str(e))
#     return result

# This is likely the exact real-world caller this class was built for — looping over IDs, calling your existing single-user deactivate_user, and routing each outcome into the accumulator.

# 11. Common beginner mistakes

# ❌ The exact bug here — calling .append() with a keyword argument, forgetting that built-in Python types have their own fixed calling conventions independent of your project's own function-writing style.

# ❌ Using = [] as a dataclass field default instead of field(default_factory=list) — causing every instance to silently share one list, a notoriously hard-to-spot bug since it often "works" until you create a second instance and watch data bleed between them.

# ❌ Applying keyword-only enforcement inconsistently across sibling methods on the same class, as seen between add_success and add_failure here.

# ❌ Reaching directly into result.succeeded.append(...) from outside the class, bypassing the dedicated method entirely — defeats the purpose of having add_success control the exact shape of what gets stored.

# 12. Think like the original developer
# What problem am I solving? "A bulk operation processes many items and needs to track which succeeded and which failed, with a reason for each failure, as one cohesive result."
# What inputs will I need? Nothing at creation time — this starts empty and gets filled in as the bulk operation runs.
# What could go wrong? Sharing a single default list across instances if built carelessly; inconsistent calling conventions between the two "add" methods; misusing a built-in list method's calling convention.
# How should I report state? Two lists, one flat (successes just need an ID) and one structured (failures need both an ID and a reason) — matching exactly how much information each outcome actually carries.
# What should happen when everything works? Each call to add_success/add_failure cleanly appends to the right list, and the whole object can be returned at the end of a bulk loop, giving the caller a complete, itemized picture of what happened.