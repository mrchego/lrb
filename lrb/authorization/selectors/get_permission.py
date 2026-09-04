from typing import Optional
from lrb.authorization.models.permission import Permission

def get_permission(*, codename:str) -> Optional[Permission]:
    return Permission.objects.filter(codename=codename).first()

# Teaching: get_permission

# This is a small selector function — matches your project's convention of separating read-only queries (selectors) from write logic (services). Let's break it down fully.

# 1. What is it?

# A function that looks up a single Permission record from the database by its codename, and returns either the found object or None if nothing matches.

# Pieces to name:

# from typing import Optional — import a type-hinting helper
# from lrb.authorization.models.permission import Permission — import your Permission model class
# def get_permission(*, codename: str) -> Optional[Permission]: — function signature with a keyword-only parameter and an "optional" return type
# Permission.objects.filter(codename=codename) — Django's query interface
# .first() — a queryset method
# 2. How is it written? (syntax piece by piece)

# from typing import Optional
# typing is a built-in Python module that provides tools purely for describing types more precisely in hints — it doesn't change how your code runs. Optional is one of those tools. You'll see why it's needed in a moment.

# * inside the parameter list

# python
# def get_permission(*, codename: str) -> Optional[Permission]:

# A bare * by itself in a parameter list is a special marker. It doesn't represent a parameter — it's a divider. Everything after it must be passed by keyword only (codename="admin.view"), never by position ("admin.view" alone). Since * is the very first thing here (before codename), it means every parameter in this function — in this case just codename — must be passed as a keyword. This matches your project's rule: all service/selector functions use keyword-only arguments.

# Why does this matter in practice? Compare:

# python
# get_permission("admin.view")           # ❌ fails — codename is keyword-only
# get_permission(codename="admin.view")  # ✅ works

# This isn't Python being strict for no reason — it's a deliberate choice your project makes (next section explains why).

# codename: str
# A type hint: "the value passed in for codename should be a string." Not enforced at runtime by Python itself — it's a promise, checked by tools like mypy or your editor, and it's documentation for humans reading the signature.

# -> Optional[Permission]
# This is the return type hint. Optional[Permission] is shorthand for "either a Permission object, or None." In older or more explicit type-hint syntax, this is identical to writing Union[Permission, None]. Optional[X] always specifically means X or None — nothing else. It exists because Python functions that search for something (and might not find it) very commonly return None on a miss, and the type hint should honestly say so, rather than just claiming -> Permission and lying about the None case.

# Permission.objects.filter(codename=codename)

# Permission — the model class itself (a blueprint for rows in the permission database table).
# .objects — every Django model automatically gets an attribute called objects, called the manager. It's your entry point into the database for that model — you never query the database directly; you go through .objects.
# .filter(codename=codename) — a method on the manager that means "find all rows where the codename column equals this value." Here, the keyword codename= refers to the model field name (a column in the database), while the value codename (no =) is your function's local variable — same word, two different roles, easy to confuse at first glance. Read it as: "filter where the database column codename equals the input codename I was given."
# .filter(...) doesn't hit the database immediately — it returns a QuerySet, which is a lazy, not-yet-executed description of a query. Django only actually talks to the database once you do something that forces evaluation, like the next call.

# .first()
# A QuerySet method that: runs the query, takes the first matching row (ordered by the model's default ordering, or database order if none is set), and returns it as a real Permission object — or returns None if there were zero matches. This is the exact behavior your -> Optional[Permission] hint promised.

# 3. Signature — broken into pieces
# python
# def get_permission(*, codename: str) -> Optional[Permission]:
# Piece	Meaning
# def	start of a function definition
# get_permission	the function's name — describes exactly what it does, nothing more
# (	start of parameter list
# *	"everything after this must be passed by keyword, not position"
# ,	separates * from the next parameter
# codename	the parameter's name — a placeholder that becomes a real value when the function is called
# : str	type hint — expects a string
# )	end of parameter list
# -> Optional[Permission]	return type hint — a Permission object, or None if not found
# :	function body starts below
# 4. Body — line by line

# There's exactly one line:

# python
# return Permission.objects.filter(codename=codename).first()

# Read right-to-left, layer by layer (matches your "read in layers, not left to right" habit):

# Innermost: codename (your local variable — whatever string was passed in when this function was called).
# Permission.objects — get the query manager for the Permission table.
# .filter(codename=codename) — build (not yet run) a query: "rows where the codename column matches."
# .first() — actually execute that query against the database, grab the first result.
# return — send that result (a Permission object, or None) back to whoever called get_permission.

# One line, but it chains four distinct operations together — this chaining style (X.Y.Z().W()) is called method chaining, and it's central to how Django's ORM (Object-Relational Mapper — the layer that turns Python code into SQL) is designed to be used.

# 5. Why?

# Why .filter().first() instead of .get(codename=codename)?
# Django also offers .get(...), which returns exactly one object or raises an exception (DoesNotExist) if there's no match, or a different exception if there's more than one match. Using .filter().first() instead is a deliberate choice: it turns "no match" into a quiet None instead of a crash. This fits a selector's job — a selector should be safe to call speculatively ("does this permission exist? let me check") without forcing every caller to wrap it in a try/except just to ask a question. Contrast this with your earlier get_current_user_or_raise — that one wants to crash (well, raise) on failure, because "no current user" really is exceptional there. Here, "no permission with that codename" might just be a normal, expected outcome the caller wants to check with a simple if.

# Why keyword-only (*,)?
# With just one parameter, it might look pointless — but it's about consistency and future-proofing. Imagine this function later grows a second parameter, like active_only: bool = True. Without the keyword-only marker, callers who wrote get_permission("admin.view") positionally could accidentally break, or new positional calls could pass values in the wrong slot without any error. Forcing codename= everywhere from day one means every call site is self-documenting (get_permission(codename="admin.view") tells you exactly what that string is, without needing to check the function definition) and safe to extend later.

# Why return Optional[Permission] instead of always raising if nothing's found?
# Selectors are meant to be cheap, side-effect-free lookups. Forcing every caller to catch an exception just to check existence would be awkward for a common pattern like:

# python
# permission = get_permission(codename="orders.delete")
# if permission is None:
#     # handle "doesn't exist" case normally, not as an error
# 6. Connections

# What comes in: a codename string — likely something like "orders.delete" or "staff.invite", matching your project's model of permissions as atomic, developer-defined capabilities (not role names).

# What goes out: a real Permission object (if the codename exists in the database) or None.

# Where this fits: this is exactly the kind of function require_permission(codename) (mentioned in your project's architecture) would likely call internally — checking "does this permission exist, and by extension, does the current user's role include it?" It's also the kind of building block an admin UI would use when assigning permissions to roles: look up the Permission object by its codename before attaching it to a role.

# Layering: get_permission → sits in lrb.authorization, imports the Permission model directly (selectors are allowed to touch models directly — that's their job; services and resolvers should go through selectors instead of touching models themselves, keeping that separation clean).

# 7. Advanced concepts

# A) Lazy QuerySets
# Permission.objects.filter(...) does not run any SQL the instant you write it. Django builds up an internal representation of the query and only sends it to the database when you do something that requires actual results — like .first(), looping over it, or converting it to a list. This matters because you can chain multiple .filter() calls together (e.g., .filter(codename=x).filter(active=True)) and Django will combine them into a single efficient SQL query, rather than running several separate queries. Recognizing "this is a QuerySet, not yet real data" versus "this triggered a real database hit" is an important skill for reading Django code and reasoning about performance.

# B) Optional[X] is really Union[X, None]
# Under the hood, Python's type system doesn't have a special "optional" concept — Optional[Permission] is literally defined as shorthand for "this value's type is either Permission or NoneType." Knowing this helps when you see the Union spelling elsewhere in code and need to recognize it's the same idea.

# C) Why .first() over indexing like [0]
# You might wonder why not Permission.objects.filter(codename=codename)[0]. [0] would raise an IndexError if there are zero results — forcing exception handling again. .first() was specifically designed by Django's authors to solve this exact "give me one, or None, safely" need — it's the idiomatic tool for exactly this shape of problem.

# 8. Small example
# python
# from typing import Optional

# class Permission:
#     def __init__(self, codename, label):
#         self.codename = codename
#         self.label = label

# fake_db = [
#     Permission("orders.delete", "Delete Orders"),
#     Permission("staff.invite", "Invite Staff"),
# ]

# def get_permission(*, codename: str) -> Optional[Permission]:
#     matches = [p for p in fake_db if p.codename == codename]
#     return matches[0] if matches else None

# found = get_permission(codename="staff.invite")
# print(found.label)          # "Invite Staff"

# missing = get_permission(codename="ghost.permission")
# print(missing)               # None
# 9. What you should remember
# *, at the start of a parameter list forces every following argument to be passed by keyword. Recognize this shape as "this function is designed for clarity/extensibility at every call site," not just a Django/DRF quirk.
# Optional[X] in a return hint is a promise: "expect X, but also handle None." Whenever you see it, the caller must be ready for a miss — don't skip the is None check.
# Model.objects.filter(...) is lazy — it builds a query, it doesn't run it. Only a method like .first(), .count(), or iterating over it actually hits the database.
# .filter().first() returns None on no match; .get() raises an exception instead. Choose based on whether "not found" is a normal case (use .filter().first()) or truly exceptional (use .get(), or your _or_raise pattern).
# Selectors stay small, side-effect-free, and return data or None — they don't raise business exceptions. That responsibility belongs to services or gatekeeper functions like get_current_user_or_raise, keeping each layer's job distinct.