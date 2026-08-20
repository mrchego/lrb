from __future__ import annotations
from django.db import transaction
from lrb.accounts.selectors.get_user import get_user
from lrb.accounts.services.ownership_guard import assert_not_last_owner
from lrb.core.exceptions import ApplicationError, ErrorCode
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lrb.accounts.models import User


@transaction.atomic
def delete_user(*, user_id: str) -> User:
    user = get_user(user_id=user_id)
    if not user:
        raise ApplicationError("User not found.", code=ErrorCode.USER_NOT_FOUND)
    if user.company_id:
        assert_not_last_owner(
            user=user, company_id=str(user.company_id), action="deleted"
        )

    user.is_active = False
    user.can_login = False
    user.save(update_fields=["is_active", "can_login"])
    return user


# 1. Purpose — Why does this exist?

# What problem is this solving?
# When someone deletes a user, you almost never want to actually erase them from the database. You want to:

# Keep their historical records (invoices, audit logs, comments) intact
# Be able to "undelete" them if it was a mistake
# Prevent them from logging in anymore

# Why not just write user.delete() directly in the view?
# Because "delete a user" isn't just one line — it's a business rule: check they exist, check they're not the last owner of a company, then deactivate them. If you scattered that logic across every view that needs to delete a user, you'd eventually forget one of those checks somewhere and create a security hole (e.g., a company with zero owners).

# When would this be used in a real project?
# Called from an API view or admin panel action: DELETE /users/<id>/.

# What happens if this code doesn't exist?
# Someone could delete the last owner of a company, leaving that company with nobody who has admin rights over it — permanently locking everyone out of managing it.

# 2. Imports — explained like you've never programmed
# python
# from django.db import transaction
# from → "go into this location and grab something specific out of it."
# django → a Python package (a folder of code) someone else wrote — the Django web framework. Not built into Python; it was pip installed.
# transaction → not the whole django.db module, just this one piece. This is a module inside django.db that deals with database transactions.

# What's a transaction, conceptually? Think of it as "all or nothing." If you're changing three things in the database and the third one fails, a transaction lets you roll back the first two so the database never ends up half-changed.

# python
# from lrb.accounts.models import User
# lrb.accounts.models — this isn't a package someone else wrote; it's part of your own project. The dots mean "folder inside folder inside folder": lrb → accounts → models.py.
# User — a class representing the database table of users. Yes, you could write your own package structured exactly like this — it's just Python files in folders with an __init__.py.
# python
# from lrb.accounts.selectors import get_user
# A "selector" in this codebase's convention is a function whose only job is reading data (as opposed to a "service," whose job is changing data). get_user presumably does User.objects.filter(id=...).first() or similar — but you don't need to know that to use it. That's the whole point of importing it: you get to treat it as a trusted tool.
# python
# from lrb.accounts.services.ownership_guard import assert_not_last_owner
# ownership_guard — a module whose entire purpose is protecting against a specific bad state: a company with no owners. assert_not_last_owner is a function that raises an error if deleting this user would leave the company ownerless.
# python
# from lrb.core.exceptions import ApplicationError, ErrorCode
# Custom exception types for this project. ApplicationError is presumably a subclass of Python's built-in Exception, and ErrorCode is likely an enum — a fixed list of named error codes (like USER_NOT_FOUND) instead of typo-prone raw strings like "user_not_found".

# Why import only transaction instead of the whole django.db?
# Because importing import django.db and then writing django.db.transaction.atomic everywhere is more typing and less readable. Pulling out exactly what you need keeps the file's "ingredient list" (its imports) an honest map of what it actually uses.

# 3. Function Signature — every symbol explained
# python
# @transaction.atomic
# def delete_user(*, user_id: str) -> User:

# @transaction.atomic
# This line above the function is called a decorator. Think of it as gift-wrapping the function: before delete_user runs, Django opens a database transaction; when it finishes (successfully or not), Django closes it. If anything inside raises an exception, everything the function did to the database gets undone. That's why it's there — this function makes multiple changes (checking ownership, then saving), and you want either all of them to happen or none.

# def
# "I'm creating a reusable block of instructions" — same as your doc explains.

# delete_user
# The function's name. Like naming a recipe: "recipe for deleting a user," not "50 lines of code that do a thing."

# (*, user_id: str)

# This is the part beginners usually skip past. Let's slow down.

# The * by itself (not attached to a name) is a special marker. It doesn't collect anything — it's a rule, not a parameter. It tells Python: "everything after this point must be passed by keyword, not by position."

# What does that mean in practice? Compare:

# python
# delete_user("abc123")        # ❌ this will ERROR
# delete_user(user_id="abc123") # ✅ this works

# Why would a developer intentionally make their function harder to call?
# Because this function might one day gain more parameters — say, deleted_by (who's performing the deletion, for audit logs). If calls were positional, delete_user("abc123", "def456") becomes ambiguous and dangerous — did you mean to delete abc123 or pass def456 as something else? Forcing keywords means every call site is self-documenting: delete_user(user_id="abc123", deleted_by="def456") can never be misread.

# user_id: str
# user_id is the parameter — a placeholder, exactly like your document's "Dear _______" example. The : str is a type hint. It doesn't force anything at runtime — Python will happily accept delete_user(user_id=123) (an int) without complaint. It's purely documentation for humans and for tools like linters/IDEs, saying "this is meant to be a string."

# -> User
# Another type hint — this time on the return value. It says "this function will hand you back a User object when it's done." Again, this doesn't change runtime behavior at all; Python won't check it. It exists so that anyone reading result = delete_user(user_id="abc123") immediately knows result is a User, without having to read the function body.

# 4. Body — line by line
# Line 1
# python
# user = get_user(user_id=user_id)

# Right side first: get_user(user_id=user_id) — call the imported selector, asking it to look up a user by this ID. We don't know or care how it looks it up (filter? get_or_none?) — that's hidden inside get_user, and that's a feature, not a mystery. This function only needs to know what it gets back, not how.

# Left side: store whatever comes back — which could be an actual User object, or None if nothing was found — in a variable named user.

# Whole line: "Try to find the user with this ID. Whatever you get (a user or nothing), remember it as user."

# Line 2–3
# python
# if not user:
#     raise ApplicationError("User not found.", code=ErrorCode.USER_NOT_FOUND)

# Verb: raise — stop execution immediately and report a problem.
# Condition: not user — this is True when user is None (or any other "falsy" value). So: "if we didn't find anybody..."
# Sentence: "If no user was found, stop everything and report a USER_NOT_FOUND error with the message 'User not found.'"

# Why check this at all, instead of just letting the next lines crash with an AttributeError?
# Because AttributeError: 'NoneType' object has no attribute 'comapny_id' is a confusing crash for whoever's calling this (a frontend developer, an API consumer). ApplicationError with ErrorCode.USER_NOT_FOUND is a controlled, expected, readable failure that can be turned into a clean 404 Not Found HTTP response.

# Line 4–7
# python
# if user.comapny_id:
#     assert_not_last_owner(
#         user=user, company_id=str(user.company_id), action="deleted"
#     )

# Condition: user.comapny_id — access the attribute comapny_id on the user object. If it's truthy (not None, not 0, not empty), enter the block.

# ⚠️ Stop — before I explain further, notice something: this says comapny_id, but two lines later it says user.company_id — spelled correctly. That's almost certainly a typo bug, not intentional. I'll cover this in "Common Mistakes" below because it's a great teaching example of exactly the kind of bug this reading process helps you catch.

# Assuming it were spelled consistently: "If this user belongs to a company..."

# Inside the block: call assert_not_last_owner, passing three named arguments: user (the whole user object), company_id (converted to a string with str() — probably because the underlying field is a UUID object, not already a string, and the function expects text), and action="deleted" (probably used to build a human-readable error message like "Cannot be deleted: last owner of company X").

# Why call str() on company_id but not on user_id earlier?
# Because user_id came in as a str already (per the type hint), while user.company_id is likely a database foreign key, which Django often represents as a UUID object internally, not plain text. Converting keeps assert_not_last_owner's contract simple: "I always receive a string."

# Whole block: "If this user is attached to a company, make sure deleting them wouldn't leave that company without any owner — and if it would, this call will raise its own error and stop everything here."

# Line 8–10
# python
# user.is_active = False
# user.can_login = False
# user.save(update_fields=["is_active", "can_login"])

# First two lines: set two attributes on the user object in memory. At this point, nothing in the database has changed yet — this is just changing a Python object sitting in memory.

# Third line — the interesting one:

# Who? user (the object).
# Verb? save() — write this object's data to the database.
# Input? update_fields=["is_active", "can_login"].

# Why pass update_fields instead of just user.save()?
# Without it, Django would UPDATE every column on that row, even ones you didn't touch. That's wasteful, and worse — if another process changed a different field on this same row between when you loaded it and when you save it, a bare .save() could silently overwrite that other process's change. update_fields tells Django: "only touch these two columns, leave everything else alone." This is a real, deliberate performance-and-safety choice, not decoration.

# Sentence for the whole block: "Mark this user as inactive and unable to log in, then write only those two changes to the database."

# Line 11
# python
# return user

# Hand the (now-modified) user object back to whoever called this function — matching the -> User promise made in the signature.

# 5. Design Discussion — why was it built this way?

# Why soft-delete (is_active = False) instead of user.delete()?
# Trade-off: .delete() is irreversible and can cascade — deleting related rows (their comments, their invoices) depending on on_delete settings, potentially destroying data you needed to keep for legal/audit reasons. Soft-delete keeps everything, costs a little extra storage, and is reversible.

# Why two separate flags, is_active and can_login, instead of one?
# This hints the codebase distinguishes "this account is archived" from "this account cannot authenticate" — they might not always change together elsewhere in the codebase (e.g., a suspended-but-still-existing user).

# Why check assert_not_last_owner before mutating anything, and why does the whole function sit inside @transaction.atomic?
# Even though the ownership check happens first here, the atomic decorator is cheap insurance: if this function grows (e.g., adds "also deactivate their API keys" as a third .save() call) and one of those later steps fails, atomic guarantees you don't end up with a user who's is_active=False but can_login=True — a broken half-state.

# 6. Common Beginner Mistakes (including a real one in this code!)

# ❌ The comapny_id / company_id typo. Line 4 checks user.comapny_id but line 5 uses user.company_id. If the User model doesn't actually have a field called comapny_id, this will raise an AttributeError at runtime — or worse, if Django models silently return None for unknown attributes in some custom __getattr__ setup (rare, but possible), it could silently skip the ownership check entirely for every user, letting the last owner of any company get deleted. This is worth double-checking against your actual model field name immediately.

# ❌ Forgetting update_fields and calling a bare .save() — as explained above, risks clobbering concurrent changes.

# ❌ Catching every exception broadly around get_user instead of explicitly checking if not user: — hides real bugs (like a database connection error) behind a generic "not found."

# ❌ Doing the ownership check after mutating the user instead of before — since Django hasn't hit the database yet at that point, it's cheap to bail out early, and it also avoids leaving user in a confusing "modified but not saved" in-memory state if the guard raises.

# 7. DIY Recipe — how you'd design a "safe delete" function yourself
# Look up the thing you want to delete. If it doesn't exist, stop immediately with a clear, typed error.
# Ask: does deleting this break an invariant elsewhere in the system? (Here: "would this leave a company without an owner?") Write a dedicated guard function for that check, so it can be reused everywhere deletion might happen (bulk delete, admin panel, API).
# Decide: hard delete or soft delete? If the data has any legal, financial, or audit significance — soft-delete.
# Wrap the whole thing in a transaction if it involves more than one database write, so partial failures can't leave corrupted state.
# Return the affected object, so callers can build a response (e.g., serialize it back to JSON confirming what got deleted).
# 8. Real Project Usage

# This exact pattern — selector → guard → mutate → save(update_fields=...) — is the shape you'll see repeated for almost every "service" function in a Django project organized this way (this looks like it follows the popular HackSoft Django Styleguide convention: selectors.py for reads, services.py for writes). You'd call delete_user from:

# A DRF APIView or ViewSet.destroy() method
# A Django admin custom action
# A management command for bulk cleanup

# Want me to go the same depth on assert_not_last_owner next (since that's the real RBAC-flavored piece — the "is this the last owner" guard), or do you want to fix the comapny_id typo first and move to another file?
