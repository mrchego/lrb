import strawberry

from lrb.accounts.selectors.get_current_user_or_raise import get_current_user_or_raise
from lrb.authorization.decorators import require_owner
from lrb.authorization.graphql.inputs import (
    AssignRoleInput,
    BulkAssignRoleInput,
    BulkRemoveRoleInput,
    ClearPermissionOverrideInput,
    CloneRoleInput,
    CreateRoleInput,
    DeleteRoleInput,
    RemoveRoleInput,
    SetPermissionOverrideInput,
    UpdateRoleInput,
)
from lrb.authorization.graphql.payloads import (
    AssignmentMutationPayload,
    RoleMutationPayload,
)
from lrb.authorization.services.assign_role import assign_role as assign_role_action
from lrb.authorization.services.bulk_assign_role import (
    bulk_assign_role as bulk_assign_role_action,
)
from lrb.authorization.services.bulk_remove_role import (
    bulk_remove_role as bulk_remove_role_action,
)
from lrb.authorization.services.clear_permission_override import (
    clear_permission_override as clear_permission_override_action,
)
from lrb.authorization.services.clone_role import clone_role as clone_role_action
from lrb.authorization.services.delete_role import delete_role as delete_role_action
from lrb.authorization.services.create_role import create_role as create_role_action
from lrb.authorization.services.remove_role import remove_role as remove_role_action
from lrb.authorization.services.set_permission_override import (
    set_permission_override as set_permission_override_action,
)
from lrb.authorization.services.update_role import update_role as update_role_action
from lrb.core.exceptions import ApplicationError
from lrb.core.graphql.errors import format_application_error
from lrb.core.graphql.payloads import BulkActionPayload, to_bulk_payload


@strawberry.type
class RoleMutation:
    @strawberry.mutation
    @require_owner()
    def create_role(
        self, info: strawberry.Info, input: CreateRoleInput
    ) -> RoleMutationPayload:
        current = get_current_user_or_raise(info)
        try:
            role = create_role_action(
                company=current.company,
                name=input.name,
                permission_codenames=input.permission_codenames,
                is_default=input.is_default,
            )
            return RoleMutationPayload(success=True, role=role)
        except ApplicationError as e:
            return RoleMutationPayload(
                success=False, errors=[format_application_error(e)]
            )

    @strawberry.mutation
    @require_owner()
    def update_role(
        self, info: strawberry.Info, input: UpdateRoleInput
    ) -> RoleMutationPayload:
        current = get_current_user_or_raise(info)
        try:
            role = update_role_action(
                role_id=input.role_id,
                company_id=str(current.company_id),
                name=input.name,
                permission_codenames=input.permission_codenames,
                is_default=input.is_default,
            )
            return RoleMutationPayload(success=True, role=role)
        except ApplicationError as e:
            return RoleMutationPayload(
                success=False, errors=[format_application_error(e)]
            )

    @strawberry.mutation
    @require_owner()
    def delete_role(
        self, info: strawberry.Info, input: DeleteRoleInput
    ) -> AssignmentMutationPayload:
        current = get_current_user_or_raise(info)
        try:
            delete_role_action(
                role_id=input.role_id, company_id=str(current.company_id)
            )
            return AssignmentMutationPayload(success=True)
        except ApplicationError as e:
            return AssignmentMutationPayload(
                success=False, errors=[format_application_error(e)]
            )

    @strawberry.mutation
    @require_owner()
    def clone_role(
        self, info: strawberry.Info, input: CloneRoleInput
    ) -> RoleMutationPayload:
        current = get_current_user_or_raise(info)
        try:
            role = clone_role_action(
                role_id=input.role_id,
                company_id=str(current.company_id),
                new_name=input.new_name,
            )
            return RoleMutationPayload(success=True, role=role)
        except ApplicationError as e:
            return RoleMutationPayload(
                success=False, errors=[format_application_error(e)]
            )

    @strawberry.mutation
    @require_owner()
    def assign_role(
        self, info: strawberry.Info, input: AssignRoleInput
    ) -> AssignmentMutationPayload:
        current = get_current_user_or_raise(info)
        try:
            assign_role_action(
                user_id=input.user_id,
                role_id=input.role_id,
                company_id=str(current.company_id),
            )
            return AssignmentMutationPayload(success=True)
        except ApplicationError as e:
            return AssignmentMutationPayload(
                success=False, errors=[format_application_error(e)]
            )

    @strawberry.mutation
    @require_owner()
    def remove_role(
        self, info: strawberry.Info, input: RemoveRoleInput
    ) -> AssignmentMutationPayload:
        current = get_current_user_or_raise(info)
        try:
            remove_role_action(
                user_id=input.user_id,
                role_id=input.role_id,
                company_id=str(current.company_id),
            )
            return AssignmentMutationPayload(success=True)
        except ApplicationError as e:
            return AssignmentMutationPayload(
                success=False, errors=[format_application_error(e)]
            )

    @strawberry.mutation
    @require_owner()
    def bulk_assign_role(
        self, info: strawberry.Info, input: BulkAssignRoleInput
    ) -> BulkActionPayload:
        current = get_current_user_or_raise(info)
        result = bulk_assign_role_action(
            user_ids=input.user_ids,
            role_id=input.role_id,
            company_id=str(current.company_id),
        )
        return to_bulk_payload(result=result)

    @strawberry.mutation
    @require_owner()
    def bulk_remove_role(
        self, info: strawberry.Info, input: BulkRemoveRoleInput
    ) -> BulkActionPayload:
        current = get_current_user_or_raise(info)
        result = bulk_remove_role_action(
            user_ids=input.user_ids,
            role_id=input.role_id,
            company_id=str(current.company_id),
        )
        return to_bulk_payload(result)

    @strawberry.mutation
    @require_owner()
    def set_permission_override(
        self, info: strawberry.Info, input: SetPermissionOverrideInput
    ) -> AssignmentMutationPayload:
        try:
            set_permission_override_action(
                user_id=input.user_id,
                permission_codename=input.permission_codename,
                is_granted=input.is_granted,
            )
            return AssignmentMutationPayload(success=True)
        except ApplicationError as e:
            return AssignmentMutationPayload(
                success=False, errors=[format_application_error(e)]
            )

    @strawberry.mutation
    @require_owner()
    def clear_permission_override(
        self, info: strawberry.Info, input: ClearPermissionOverrideInput
    ) -> AssignmentMutationPayload:
        try:
            clear_permission_override_action(
                user_id=input.user_id, permission_codename=input.permission_codename
            )
            return AssignmentMutationPayload(success=True)
        except ApplicationError as e:
            return AssignmentMutationPayload(
                success=False, errors=[format_application_error(e)]
            )


# Teaching: RoleMutation

# This is the final piece of the whole picture — the write-side counterpart to RoleQuery, tying together nearly every service, input, and payload type you've read across this entire conversation. Structurally it's almost identical to UserMutation (your very first file), so I won't re-teach @strawberry.mutation, @require_owner(), try/except ApplicationError, or the payload pattern. Instead: one new syntax detail (import ... as ...), and — this file has two separate, real bugs, one of which is a direct, satisfying payoff of something you flagged yourself two functions ago.

# 1. What is it?

# A GraphQL mutation class exposing every write operation for roles and permission overrides — create_role, update_role, delete_role, clone_role, assign_role, remove_role, the two bulk operations, and the two permission-override operations. Every method here is a resolver that authenticates (mostly), calls a service you've already fully learned, and wraps the result in a payload.

# New piece: import X as Y.

# 2. How is it written?

# from lrb.authorization.services.assign_role import assign_role as assign_role_action
# This is import aliasing — the as keyword lets you rename something at the moment you import it. Without the alias, this line would just be from ... import assign_role, and inside this file you'd call it as assign_role(...). But look at this class: it also defines a method named assign_role (def assign_role(self, info, input): ...). If both the imported service function and the resolver method were named assign_role in the same scope, the method definition would shadow the import — the exact same "later name wins" collision you personally diagnosed in the UserPermissionOverride GraphQL types file. Aliasing the import to assign_role_action sidesteps that collision entirely: the resolver method keeps the clean, GraphQL-facing name assign_role (matching the GraphQL schema's mutation name), while the underlying service function gets a distinct name (assign_role_action) that can never clash with it. This pattern repeats for every service imported here that shares a name with its resolver method: bulk_assign_role_action, bulk_remove_role_action, clear_permission_override_action, delete_role_action, create_role_action, remove_role_action, set_permission_override_action, update_role_action.

# Worth noticing what does not get aliased: clone_role is imported as plain clone_role (no as), even though the resolver method below it is also named clone_role. Let's check whether that's actually a problem — see section 5, it's the first thing worth flagging.

# Everything else in this file — the resolvers' bodies — is a direct, mechanical application of everything you already know: get_current_user_or_raise(info), calling a service with keyword arguments, wrapping the result in a payload, catching ApplicationError.

# 3. Signature — one representative example
# python
# def create_role(
#     self, info: strawberry.Info, input: CreateRoleInput
# ) -> RoleMutationPayload:

# Identical shape to every mutation you've read since UserMutation — self, info, input in, a *Payload type out. Nothing new to break down here; you should read this instantly by now.

# 4. Body — the two real bugs in this file

# Bug 1 — clone_role's naming collision, and why it "gets away with it"

# python
# from lrb.authorization.services.clone_role import clone_role
# ...
# @strawberry.mutation
# @require_owner()
# def clone_role(
#     self, info: strawberry.Info, input: CloneRoleInput
# ) -> RoleMutationPayload:
#     current = get_current_user_or_raise(info)
#     try:
#         role = clone_role(
#             role_id=input.role_id,
#             company_id=str(current.company_id),
#             new_name=input.new_name,
#         )

# Here's the sequence: the module-level import binds the name clone_role to the service function. Then, def clone_role(self, info, input): — the method definition — reassigns the name clone_role, at module/class-definition scope, to the method itself, exactly the shadowing mechanic from your GraphQL types file.

# But wait — inside the method's own body, it calls clone_role(role_id=..., ...). Does this call the service, or does it (impossibly) try to call itself? It calls the service correctly, and here's the subtle reason why: Python resolves names at the moment a line actually runs, and it looks them up according to scope — first checking local variables inside the function, then the enclosing scope, then the module's global scope. Inside create_role's method body, clone_role is not a local variable — so Python looks it up in the module's global namespace at the time the call executes. By the time any resolver method actually gets called (i.e., when a real GraphQL request comes in, long after the whole file has finished being defined), the module's global name clone_role has already been overwritten by the class attribute definition process — but only within the class body's own scope, not the module's global scope. Methods defined inside a class body do not, themselves, rebind names in the module's global namespace — def clone_role(...): inside class RoleMutation: creates an attribute of the class (RoleMutation.clone_role), not a new global name. The module-level global clone_role (bound by the import line) is untouched.

# So: this actually works correctly, by luck of Python's scoping rules for classes — but it's fragile and confusing to read, exactly the same category of risk as the collision you caught in the GraphQL types file, even though this particular instance doesn't cause a runtime bug. This is precisely why every other service in this file was aliased with as ..._action — someone clearly understood the risk and defended against it everywhere else, but missed this one case. The fix, for consistency and to remove any doubt for a future reader:

# python
# from lrb.authorization.services.clone_role import clone_role as clone_role_action
# ...
# role = clone_role_action(...)

# Bug 2 — wrong return type hints on the bulk mutations

# python
# @strawberry.mutation
# @require_owner()
# def bulk_assign_role(
#     self, info: strawberry.Info, input: BulkAssignRoleInput
# ) -> BulkAssignRoleInput:          # <-- look closely
#     current = get_current_user_or_raise(info)
#     result = bulk_assign_role_action(...)
#     return to_bulk_payload(result=result)

# The return type hint says -> BulkAssignRoleInput — but BulkAssignRoleInput is an input type (the very thing this method receives as its input parameter!), not an output/payload type. The actual value being returned, to_bulk_payload(result=result), is almost certainly a BulkActionPayload (the type you saw referenced back in your very first UserMutation file). This is a copy-paste mistake — likely from duplicating the method signature and forgetting to change the return annotation from the input class name to the correct payload class name. The exact same bug repeats in bulk_remove_role:

# python
# ) -> BulkRemoveRoleInput:   # should be -> BulkActionPayload

# Why this actually matters, not just "wrong-looking": Strawberry builds its GraphQL schema directly from these type hints. Declaring a mutation's return type as an input type is not just semantically odd — GraphQL's type system genuinely separates input and output types (you learned this distinction explicitly in the inputs-file lesson), so this would very likely cause a schema-build error when Strawberry tries to construct the GraphQL schema, since BulkAssignRoleInput was declared with @strawberry.input, not @strawberry.type, and isn't valid in an output position at all. The fix:

# python
# from lrb.core.graphql.payloads import BulkActionPayload
# ...
# def bulk_assign_role(self, info, input: BulkAssignRoleInput) -> BulkActionPayload:
# 5. Why? — and a third, more serious gap worth tracing back

# A gap you should catch yourself first: look at set_permission_override and clear_permission_override.

# python
# @strawberry.mutation
# @require_owner()
# def set_permission_override(
#     self, info: strawberry.Info, input: SetPermissionOverrideInput
# ) -> AssignmentMutationPayload:
#     try:
#         set_permission_override_action(
#             user_id=input.user_id,
#             permission_codename=input.permission_codename,
#             is_granted=input.is_granted,
#         )
#         return AssignmentMutationPayload(success=True)
#     except ApplicationError as e:
#         return AssignmentMutationPayload(success=False, errors=[format_application_error(e)])

# Compare this against every other method in this file: every single one of them starts with current = get_current_user_or_raise(info). These two methods — set_permission_override and clear_permission_override — don't call it at all.

# Now connect this directly back to what you flagged yourself, two files ago, reading set_permission_override (the service) and clear_permission_override (the service): you noticed both services accept no company_id and have no scoping check, and you specifically wrote "worth tracing this function's actual callers to confirm the company check happens somewhere before this runs — never assume it does just because the function is named sensibly."

# You now have the answer, and it's bad news: the company check does not happen anywhere. The resolver never fetches current at all, so there's no current.company_id available even if the service did accept one. Combined with @require_owner() (which — as you reasoned back in your very first file — checks that the caller has owner-level permission, but says nothing about which company they're an owner of, if your data model allows an owner to belong to exactly one company, this might be a non-issue in practice, but it's still worth being certain about, not assumed), this means: any authenticated owner-level user, from any company, can call setPermissionOverride with an arbitrary user_id and grant or revoke any permission for a user belonging to a completely different company. This is a real, serious, exploitable gap — precisely the kind of thing your own earlier instinct to "trace the caller" was built to catch, and tracing it just confirmed the worst case.

# The fix would need two things: fetch current (for consistency, and to actually have something to scope with), and — more importantly — the underlying services (set_permission_override, clear_permission_override) would need to be updated to accept and check company_id, matching the pattern every other scoped service in this project already follows (get_role, assign_role, remove_role, delete_role). The resolver fix alone isn't enough; the gap runs all the way down to the service layer, which is exactly what you predicted when you first read those two files.

# 6. Connections

# This file is the true "final assembly point" for nearly everything read across this entire conversation: every input type feeds a method here; every service you've studied gets called from exactly one method here; every payload type gets constructed and returned from here. If you trace a single GraphQL mutation request end to end — CreateRoleInput → create_role resolver → create_role_action service → Role.objects.create(...) → RoleMutationPayload → back to the client — you're tracing a path built entirely from files you've now read and understood in this one long conversation.

# 7. Advanced concepts

# A) Class-body scoping vs. module-level scoping — why clone_role's naming collision didn't actually break anything
# This is worth sitting with, because it's genuinely subtle: defining a method inside a class body does not rebind names in the module's global namespace, even though defining a top-level class SomeName: (like the earlier UserPermissionOverride example) does rebind the module-global name. The difference is where the definition happens — directly at module level (dangerous, causes real shadowing) versus nested inside a class body (the name becomes an attribute of the class object, not a new module global). This is exactly why the earlier UserPermissionOverride bug was real and dangerous, while this file's clone_role situation, though confusingly similar-looking, doesn't actually break at runtime — same surface pattern, genuinely different consequence, because of where the redefinition happens.

# B) Aliasing as defensive naming, applied inconsistently
# The as ..._action pattern used throughout this file (assign_role_action, update_role_action, etc.) is a good, deliberate defensive habit — but it's only as protective as its consistent application. One missed case (clone_role) doesn't cause a bug here, but it does mean a future reader can't trust "every service import in this file is safely aliased" as a blanket assumption — they'd have to check each one individually, which defeats some of the purpose of establishing the convention in the first place.

# C) Tracing a flagged concern to its actual resolution — the real skill this whole conversation has built
# The set_permission_override/clear_permission_override gap is the best example in this entire conversation of why the "trace this before assuming it's safe" instinct matters. Two files ago, you correctly refused to assume the gap was fine just because a function looked reasonable in isolation. Here, tracing forward confirmed it wasn't fine. This is the core discipline of reading real code for security-relevant behavior: a concern flagged in one file is not resolved until you've actually followed it to where it either gets handled, or doesn't.

# 8. Small example (demonstrating the class-scoping subtlety)
# python
# def helper():
#     return "module-level helper"

# class Thing:
#     def helper(self):          # does NOT overwrite the module-level `helper`
#         return helper() + " called from inside a method"   # calls the MODULE-level one!

# t = Thing()
# print(t.helper())              # "module-level helper called from inside a method"
# print(helper())                # "module-level helper" — untouched
# 9. What you should remember
# import X as Y is a defensive tool for avoiding name collisions between an imported function and a same-named method/variable defined later in the same file — recognize the pattern, and notice when it's applied inconsistently (as with the missed clone_role case here).
# A method defined inside a class body does not rebind the module's global namespace — this is why clone_role's apparent self-collision doesn't actually break at runtime, unlike a top-level class SomeName: redefinition (which does overwrite the global name, as you saw in the GraphQL types file). Same-looking pattern, different scope, different consequence — worth knowing the distinction precisely.
# A resolver's return type hint must be an output type, never an input type — -> BulkAssignRoleInput instead of -> BulkActionPayload isn't just a style slip; GraphQL's input/output type separation means this would very likely break schema construction entirely.
# A flagged security concern isn't resolved until you've traced it to its actual call site — the missing company_id scoping you first questioned in the service files is confirmed here as a real, exploitable gap, because the resolver never even fetches the current user to scope anything with in the first place.
# Comparing a file against its own established internal pattern (every other method calls get_current_user_or_raise; these two don't) is often the fastest way to spot a real gap — you didn't need to know anything new to catch this; you just needed to keep applying the same "compare against siblings" discipline you've built across this entire conversation, right through to the very last file.