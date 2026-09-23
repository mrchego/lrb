from django.db import transaction
from django.utils import timezone

from lrb.authorization.services.assign_role import assign_role
from lrb.core.exceptions import ApplicationError, ErrorCode
from lrb.identity.services.change_password import set_password_unchecked
from lrb.staff.models import Invitation


@transaction.atomic
def accept_invitation(*, token, new_password):
    invitation = (
        Invitation.objects.select_for_update().filter(token=token, used=False).first()
    )
    if not invitation:
        raise ApplicationError(
            message="Invalid or expired invitation token.", code=ErrorCode.INVALID_TOKEN
        )

    if invitation.is_expired:
        raise ApplicationError(
            message="This invitation has expired. Ask an admin to resend it.",
            code=ErrorCode.INVALID_TOKEN,
        )

    user = invitation.company.users.filter(email=invitation.email).first()
    if not user:
        raise ApplicationError(
            message="User no longer exists.", code=ErrorCode.USER_NOT_FOUND
        )

    set_password_unchecked(user=user, new_password=new_password)
    user.can_login = True
    user.is_active = True
    user.save(update_fields=["can_login", "is_active"])

    if invitation.role_id:
        assign_role(
            user_id=user.id,
            role_id=invitation.role_id,
            company_id=invitation.company_id,
        )

    invitation.used = True
    invitation.accepted_at = timezone.now()
    invitation.save(update_fields=["used", "accepted_at"])
    return user


# Great question — and worth being precise about, because there are actually two separate kinds of "execution order" happening here, and conflating them is a common source of confusion. Let's separate them, then trace this exact file through both.

# Phase 1: Import time — runs once, when the file is first loaded

# This happens before accept_invitation is ever called — the moment something, somewhere, first does import on this module (directly or indirectly).

# python
# from django.db import transaction
# from django.utils import timezone
# from lrb.authorization.services.assign_role import assign_role
# from lrb.core.exceptions import ApplicationError, ErrorCode
# from lrb.identity.services.change_password import set_password_unchecked
# from lrb.staff.models import Invitation

# Python runs these top to bottom, one at a time. Each line goes and finds the named module, loads that module fully (running its imports first, if it hasn't been loaded already), then binds the requested name (transaction, timezone, assign_role, etc.) into this file's namespace. This only ever happens once per process — Python caches loaded modules, so even if a hundred other files also import this same module later, these six lines don't re-run each time.

# python
# @transaction.atomic
# def accept_invitation(*, token, new_password):
#     ...

# This part is worth slowing down on, because it's a common misconception: the function body does not run at import time. What does run at import time is the def statement itself — Python builds the function object (compiling its body into bytecode, but not executing that bytecode), and then immediately applies the decorator: accept_invitation = transaction.atomic(accept_invitation). So by the end of import time, you have one thing sitting in memory: a decorated, callable function object named accept_invitation, ready to be called — but nothing inside it has run yet.

# Phase 2: Call time — runs every single time someone calls accept_invitation(token=..., new_password=...)

# This is the part you're really asking about, and this is where the interesting step-by-step behavior lives. Let's trace one real call.

# Step 1 — the decorator wrapper takes control first.
# Because of @transaction.atomic, the actual function that gets called isn't your accept_invitation code directly — it's a wrapper Django built around it. That wrapper's first move is to open a database transaction (roughly: tell the database "hold everything I'm about to do; don't make any of it permanent until I say so"). Only after that transaction is open does the wrapper call your real function body.

# Step 2 — the query executes, and a row gets locked.

# python
# invitation = (
#     Invitation.objects.select_for_update().filter(token=token, used=False).first()
# )

# Here's where the "right side first" habit you already use pays off directly: Python evaluates the whole right-hand expression before assigning anything to invitation. .select_for_update() and .filter(token=token, used=False) don't touch the database yet — remember, querysets are lazy. It's .first() that actually forces evaluation: this is the exact moment SQL runs and hits the database. If a matching row is found, the database also places a row-level lock on it (because of select_for_update()) — meaning any other transaction trying to read that same row with its own select_for_update() right now has to wait until this transaction finishes. Only after all of that completes does Python assign the result — a real Invitation object, or None — to invitation.

# Step 3 — the first branch point.

# python
# if not invitation:
#     raise ApplicationError(...)

# Python evaluates not invitation. If invitation is None, this is True — the raise executes immediately. This is a real fork in execution, not just a check that gets noted and continued past. raise throws control straight out of this function entirely — every line below it in the function body never runs. Control jumps up to whatever caught this — a GraphQL resolver's except ApplicationError, most likely. And critically: because this raise happens inside an atomic block, transaction.atomic's wrapper catches the fact that an exception occurred and rolls the transaction back — anything the database might have done so far (nothing, in this branch — we've only read) gets discarded, and the lock from select_for_update() is released.

# If invitation is a real object, not invitation is False, the if block is skipped entirely, and execution just continues to the next line.

# Step 4 — same pattern, second check.

# python
# if invitation.is_expired:
#     raise ApplicationError(...)

# invitation.is_expired — this calls the @property you know from the model, which runs timezone.now() >= self.expires_at right now, live. If True, same as before: raise, unwind, rollback, done. Otherwise, continue.

# Step 5 — another query, another branch.

# python
# user = invitation.company.users.filter(email=invitation.email).first()
# if not user:
#     raise ApplicationError(...)

# invitation.company — this reaches across the foreign key. Since invitation was just loaded and company wasn't specifically pre-fetched, this triggers its own separate database query, right at this exact line, the first time .company is accessed. Then .users.filter(...).first() runs a third query. Same guard pattern as before: if nothing's found, raise and unwind everything so far.

# Step 6 — the first real write.

# python
# set_password_unchecked(user=user, new_password=new_password)

# This is a function call, not inline code — execution genuinely leaves accept_invitation and jumps into set_password_unchecked's own body (which itself calls _set_new_password, which itself validates and calls user.set_password(...) and user.save(...)). All of that runs to completion — including its own database write — and only once it returns does control come back here, to the next line.

# Step 7 — the second write, inline this time.

# python
# user.can_login = True
# user.is_active = True
# user.save(update_fields=["can_login", "is_active"])

# No branching, no function call — just three statements, one after another, changing the in-memory user object and then writing exactly those two fields to the database.

# Step 8 — a conditional call to another atomic function.

# python
# if invitation.role_id:
#     assign_role(
#         user_id=user.id,
#         role_id=invitation.role_id,
#         company_id=invitation.company_id,
#     )

# If invitation.role_id is falsy (None), this whole block is skipped — execution just drops straight to the next line below it. If it's truthy, assign_role(...) is called — and here's the nested-atomic behavior you learned about with reset_password: assign_role has its own @transaction.atomic, but since we're already inside one (the outer accept_invitation transaction opened back in Step 1), Django doesn't start a second real transaction — it creates a savepoint, a marker it could roll back to on its own if assign_role failed, without necessarily undoing everything before it. But since assign_role doesn't catch its own exceptions (any ApplicationError it raises propagates straight up), in practice here a failure inside assign_role unwinds the entire outer transaction too — same end result as if there were only one atomic block, because nothing in accept_invitation ever catches that exception to stop the unwind partway.

# Step 9 — the final write.

# python
# invitation.used = True
# invitation.accepted_at = timezone.now()
# invitation.save(update_fields=["used", "accepted_at"])

# Same pattern as Step 7 — set two attributes in memory, then persist just those two columns.

# Step 10 — return, and the transaction commits.

# python
# return user

# This is the last line reached without an exception. return user hands the user object back to @transaction.atomic's wrapper — and this is the moment the wrapper says "the function completed with no exception, so make everything durable" — it issues a COMMIT, and every write from steps 6, 7, 8, and 9 becomes permanent, all at once, together. Only then does the wrapper hand user back to whatever code originally called accept_invitation.

# The core thing worth taking away

# Reading order (imports → signature → body, top to bottom) is a great strategy for understanding a file — but actual execution order isn't a single straight line down the page. It branches at every if, it jumps out entirely on raise, it leaves and comes back on every function call (set_password_unchecked, assign_role), and the transaction wrapping the whole thing means the database-visible effect of every write is held back and only finalized — all together, or not at all — at the very end, on a clean return. "Read top to bottom" gets you a mental map of what could happen; tracing an actual call means following one specific path through that map, and asking at every line: does this raise, does this branch, does this call something else, does this write happen now or does it wait?
