from dataclasses import dataclass, field


@dataclass
class BulkActionResult:
    succeeded: list[str] = field(default_factory=list)
    failed: list[dict] = field(default_factory=list)
    
    def add_success(self, user_id: str) -> None:
        self.succeeded.append(user_id)
        
    def add_failure(self, user_id:str, reason:str) -> None:
        self.failed.append({"user_id": user_id, "reason": reason})
        
        
        
# core/results.py — BulkActionResult
# 1. Purpose (Why this exists)

# What problem is this solving?
# Imagine an admin selects 50 users and clicks "Deactivate." Some succeed, some fail (already inactive, not found, permission denied). You need to report back both lists — which succeeded, which failed and why — as one coherent result, not as separate scattered pieces of information floating around your code.

# Why couldn't we just write the logic directly? You could return two separate lists from a function: return succeeded, failed. But then every single caller has to remember the exact order (succeeded first? failed first?), and if you ever want to add a third piece of information (say, a count of skipped items), you'd have to change the return signature everywhere it's used — a fragile, error-prone way to pass grouped data around.

# When is this used in a real project? Any "bulk operation" — activating/deactivating many users at once, bulk-deleting roles, bulk-inviting staff members — anywhere your GraphQL API processes a list of items and needs to report per-item success/failure back to the frontend in one clean response.

# What happens if this doesn't exist? Every bulk-action service would invent its own ad-hoc way of tracking successes/failures — some using two lists, some using a dictionary, some forgetting to track failures at all — making every bulk mutation's result shape inconsistent and harder for your GraphQL schema to represent predictably.

# 2. Imports — explained like you've never programmed
# python
# from dataclasses import dataclass, field
# from — tells Python "don't bring in an entire toolbox, just specific pieces from it." Contrast with import dataclasses (the whole toolbox) versus from dataclasses import dataclass (just one tool from inside it).
# dataclasses — this is a module (a file full of pre-written code) that comes built into Python itself — you didn't install anything extra to get it; it ships with every Python installation. It exists because Python's creators noticed programmers kept writing the exact same repetitive pattern over and over — a class whose entire job is just "hold some named pieces of data" — and built a shortcut so you don't have to hand-write that boilerplate every time.
# import — "bring the named tool(s) into this file so I can use them below."
# dataclass — one specific tool from that module: a decorator (a special marker you put above a class using @) that tells Python "auto-generate the repetitive setup code for this class for me."
# field — a second tool from the same module, used to give Python extra, more specific instructions about how one particular piece of data on the class should be created — we'll see exactly why it's needed below.

# Could I write my own package like this? Yes — any .py file with functions/classes in it can be imported by another file, exactly the same way. dataclasses isn't magic; it's just Python code someone (the Python core team) wrote and bundled with the language.

# Why are we importing only dataclass and field instead of everything? Because those are the only two tools from that whole module this file actually needs. Importing only what you use keeps things clear — anyone reading the top of this file instantly knows "this file uses dataclasses' dataclass decorator and its field helper," nothing more.

# 3. The decorator
# python
# @dataclass

# The @ symbol means "apply this decorator to the thing defined right below it" — same mechanic as @shared_task and @wraps(func) from earlier files, just a different decorator doing a different job. Here, it tells Python: "generate the repetitive setup code (like __init__) for this class automatically, based on the fields I list below."

# What does it generate? Without @dataclass, you'd have to hand-write:

# python
# class BulkActionResult:
#     def __init__(self, succeeded=None, failed=None):
#         self.succeeded = succeeded if succeeded is not None else []
#         self.failed = failed if failed is not None else []

# @dataclass writes something equivalent to this for you automatically, just from the field declarations below — saving real typing and reducing the chance of a typo in boilerplate you'd otherwise write by hand every time.

# 4. The class
# python
# class BulkActionResult:

# Why a class, not just functions? Because this represents one bundle of related data that changes together and gets passed around as a unit — a succeeded list and a failed list that always belong together, conceptually, as "the result of one bulk action." A class lets you create many separate, independent instances of this bundle (one per bulk operation you run), each with its own private data.

# What is an object? What is an instance? The class BulkActionResult is a blueprint — instructions for building something, not the thing itself (same "house blueprint vs. actual house" idea). When you write result = BulkActionResult(), you're building one actual, real object from that blueprint — that specific object is called an "instance" of the class. You could build several instances (result1 = BulkActionResult(), result2 = BulkActionResult()), and each one has its own separate succeeded/failed lists, completely independent of each other.

# Why is self needed? Because a class's methods need a way to say "modify this particular instance's data, not some other instance's." self, inside any method, always refers to "whichever specific instance this method was called on." result1.add_success("A") and result2.add_success("B") both run the same method code, but self is different each time, so each instance's own list gets updated, not the other's.

# 5. The fields — line by line
# python
#     succeeded: list[str] = field(default_factory=list)

# Right side first: field(default_factory=list) — this tells @dataclass: "don't just set a plain default value directly. Instead, every time someone creates a new BulkActionResult, call the function list (with no arguments — which produces a brand new empty list, []) and use that as this field's starting value."

# Why not just write succeeded: list = []? Because lists are mutable — meaning they can be changed after creation. If you wrote a plain = [] default, Python would create that one empty list once, at the moment the class itself is defined — and every single instance you ever create would then share that same one list behind the scenes. If result1.add_success("A") ran, result2.succeeded would mysteriously also contain "A" — a very confusing, hard-to-track bug. default_factory=list fixes this by creating a genuinely fresh, separate empty list for every new instance.

# Left side: succeeded: list[str] — succeeded is the attribute's name; : list[str] is a type hint meaning "this should be a list containing strings" (Python doesn't force this at runtime — it's documentation for you and your tools, not an enforced rule).

# Whole line, in plain English: "Every BulkActionResult gets its own attribute called succeeded, starting as a brand-new empty list, meant to hold strings."

# python
#     failed: list[dict] = field(default=list)

# I need to stop here — this line has a real bug, and it's worth working through why, not just accepting it. Compare it carefully to the line above:

# Line 1 uses default_factory=list.
# Line 2 uses default=list — a different keyword entirely, and it's wrong.

# What does default=list actually do? default= (without _factory) tells @dataclass: "use this exact value as the default, literally, every time." But look at what's being handed to it: not list() (calling the function to get an empty list), just the bare word list — a reference to the list type/class itself, not an actual list. So every new BulkActionResult instance's failed attribute would default to holding the list class itself — not [], not any kind of usable list. The very first time any code tried to do self.failed.append(...), it would crash, because you cannot call .append() on the list type itself — only on an actual list instance.

# The fix:

# python
#     failed: list[dict] = field(default_factory=list)

# Matching the pattern from the line above — default_factory=list, exactly like succeeded.

# Why does this matter as a beginner lesson? This is exactly the kind of subtle, easy-to-miss typo we found in ApplicationError's trailing comma — one word different (default vs default_factory), no crash at class-definition time, but a real, guaranteed failure the moment add_failure actually runs.

# 6. The methods
# python
#     def add_success(self, user_id: str) -> None:
#         self.succeeded.append(user_id)

# Signature, piece by piece:

# def — "I'm defining a reusable block of instructions."
# add_success — its name; a method (a function that lives inside a class and operates on a specific instance).
# (self, user_id: str) — self (the instance this runs on, explained above), plus one real input, user_id, expected to be a string.
# -> None — a return type hint meaning "this method doesn't hand anything back." It exists purely to change the object's own data (a "side effect"), not to compute and return a new value.

# Body, right side then left side then whole line:
# self.succeeded.append(user_id) — read the chain left to right as a journey: start at self (this specific instance) → go to its succeeded list → call .append() on that list (a built-in list method meaning "add one item onto the end") → the thing being added is user_id.

# Whole line in plain English: "Add this user_id onto the end of this instance's own succeeded list."

# python
#     def add_failure(self, user_id: str, reason: str) -> None:
#         self.failed.append({"user_id": user_id, "reason": reason})

# Same shape, but with two inputs (user_id, reason), and instead of appending a plain string, it builds a small dictionary — {"user_id": user_id, "reason": reason} — pairing the failed user's ID with why they failed, then appends that whole dictionary onto self.failed.

# 7. Beginner questions, answered

# Why parentheses after field? Same reason as any function call — parentheses are where you hand a function its inputs. field(default_factory=list) is calling the field function, handing it one named input.

# Why square brackets in list[str]? This is Python's syntax for saying "a list, specifically containing this type of thing." list[str] = "a list of strings." list[dict] = "a list of dictionaries."

# Why curly braces in {"user_id": user_id, "reason": reason}? Curly braces {} build a dictionary — a collection of key: value pairs. "user_id" is the key (always in quotes, since it's literal text), and user_id (no quotes) is the variable, whose current value gets stored under that key.

# Why colons in succeeded: list[str]? This specific colon isn't dictionary syntax — it's a type hint separator: "the name on the left should hold a value of the type on the right."

# Why not just write directly to the lists everywhere, like result.succeeded.append(user_id), instead of calling add_success()? Covered fully in Design Discussion below.

# 8. Design Discussion

# Why add_success()/add_failure() methods instead of letting callers touch .succeeded/.failed directly?

# This gives you one single, controlled place where "a success gets recorded" happens. Right now, that's just one line (.append(...)). But imagine later you decide every success should also record a timestamp, or every failure should include an error code alongside the reason. If every caller across your project did result.succeeded.append(user_id) directly, you'd have to find and update every single call site to add that new behavior. With a method, you change add_success() once, and every caller automatically benefits — they don't even need to know anything changed.

# Trade-off: it's a tiny bit more code upfront (two small methods instead of "just append directly") for meaningfully more flexibility later. This is a very standard trade in software design — a small amount of indirection now, in exchange for a single point of control later.

# 9. General Pattern Recognition

# This file follows a very common, reusable shape:

# Group related data together (a dataclass)
#        ↓
# Give mutable fields safe, unique defaults (default_factory)
#        ↓
# Provide small methods to update that data consistently
#        ↓
# Pass the whole object around, instead of loose separate variables

# Once you recognize this shape, you can build the same kind of thing for: a SearchResult (matches + total count), a ValidationReport (passed fields + failed fields), an ImportSummary (rows imported + rows skipped) — anywhere you're currently tempted to return two or three separate loose values from a function.

# 10. Real project usage

# In your RBAC project, this would plug into a bulk mutation service — e.g., a bulk_deactivate_users service that loops over a list of user IDs, tries to deactivate each one, and calls result.add_success(user_id) or result.add_failure(user_id, reason) depending on outcome. The finished BulkActionResult object then gets handed to the GraphQL layer, which reads .succeeded and .failed to build the mutation's response payload for the frontend.

# 11. Common beginner mistakes
# ❌ Using = [] directly as a field default instead of field(default_factory=list) — causes the shared-mutable-default bug explained above.
# ❌ Using field(default=list) instead of field(default_factory=list) — the exact bug we just found and fixed in this file.
# ❌ Forgetting -> None isn't required but omitting it makes it unclear (to a reader) whether a method is meant to return something useful or just mutate the object.
# ❌ Writing self.succeeded = self.succeeded.append(user_id) — a subtle trap: .append() always returns None, so this would silently wipe out the whole list with None. .append() modifies the list in place; it doesn't need (or want) reassignment.
# 12. Think like the original developer

# If you had no reference and needed to invent this yourself, the reasoning would go:

# "I'm running an operation on many items — I need to track which succeeded and which failed."
# "Two separate lists is the simplest way to represent that."
# "I don't want to return a plain tuple of two lists, because that's easy to misuse (wrong order, unclear meaning) — I'll wrap them in an object with clear, named attributes."
# "Since I might create many of these result objects over the app's lifetime (one per bulk action), each needs its own independent lists — so I have to be careful about how I create the default value for a list field."
# "For failures, I don't just want the ID — I want to know why it failed, so I'll store a small structured piece of information (a dictionary) rather than just a string."
# "I'll add small helper methods for adding a success/failure, so there's one consistent way to update this object, rather than leaving it open for every caller to modify the internals directly."

# That thought process — from "what do I need to track" to "how do I protect against sharing/mutation bugs" to "how do I keep future changes centralized" — is exactly the reasoning that produces this file, with no external reference needed.