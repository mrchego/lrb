from django.contrib import admin
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
class BaseModelAdmin(admin.ModelAdmin):
    readonly_fields = ["id", "created_at", "updated_at"]
    list_display = ["id", "created_at", "updated_at"]
    date_hierarchy = "created_at"
    
    def get_readonly_fields(self, request, obj = None):
        fields = super().get_readonly_fields(request, obj)
        if hasattr(self.model, "deleted_at"):
            fields = list(fields) + ["deleted_at"]
        return fields
    
    def get_actions(self, request):
        actions = super().get_actions(request)
        if hasattr(self.model, "soft_delete"):
            if "delete_selected" in actions:
                del actions["delete_selected"]
            actions["soft_delete_selected"] = (
                self.soft_delete_selected,
                "soft_delete_selected",
                _("Soft delete selected items")
            )
        return actions
    
    def soft_delete_selected(self, request, queryset):
        queryset.update(is_deleted=True, deleted_at=timezone.now())
    soft_delete_selected.short_description = _("Soft delete selected items")
    
    
# BaseModelAdmin — a reusable Django Admin base class
# 1. Purpose — What problem does this solve?

# In Django, every model you want to manage through the admin site (/admin/) normally needs its own ModelAdmin class describing how it should look — which fields are read-only, which columns show in the list view, etc.

# If your RBAC project has many models (accounts, identity, staff, products, categories, orders...) and most of them share the same base fields — id, created_at, updated_at, maybe a soft-delete flag — you'd otherwise have to repeat the same admin configuration in every single app. That's copy-paste, and copy-paste means when you want to change one thing (like adding a "soft delete" action), you'd have to update it in a dozen places.

# BaseModelAdmin solves this by being a shared parent class: every specific model's admin class can inherit from this one and automatically get consistent read-only timestamp fields, a working date filter, and — if the model supports it — a safe "soft delete" action instead of Django's default hard-delete action.

# Why not just write the logic directly in each app's admin.py? You could, but then "soft delete" behavior would live in ten different files, subtly drifting apart over time as people copy-paste-modify it. Centralizing it here means one bug fix or improvement propagates everywhere automatically.

# When is this used? Any time you register a model with Django's admin site, e.g. class OrderAdmin(BaseModelAdmin): ... — inheriting this instead of admin.ModelAdmin directly.

# What breaks without it? Nothing crashes — Django's plain admin.ModelAdmin still works. But you lose the automatic "soft delete" safety net, meaning admins could accidentally permanently delete records that your app is designed to soft-delete (keep in the DB, just flagged as hidden).

# 2. Imports — explained like you've never programmed
# python
# from django.contrib import admin
# from django.utils import timezone
# from django.utils.translation import gettext_lazy as _

# django.contrib — a section of Django containing optional, swappable "add-on" apps that ship with the framework but aren't mandatory (the admin site is one of these add-ons — you could build a Django project without ever using it).

# admin — specifically, Django's built-in admin app module. Pulling this in gives you admin.ModelAdmin, the base class Django itself provides for "how should this model look in the admin site."

# django.utils — a grab-bag module of small helper tools Django provides that aren't tied to any one specific app (dates, text, translation, etc.).

# timezone — a helper module for working with dates/times correctly, specifically ones that are aware of timezones. Plain Python's datetime.now() doesn't account for timezones properly in a way Django's settings expect; timezone.now() does.

# gettext_lazy as _ — same as your previous file: marks strings as translatable, without translating immediately.

# Why timezone.now() instead of Python's built-in datetime.now()? Because Django projects are usually configured with USE_TZ = True, meaning all datetimes stored in the database are expected to carry timezone info. datetime.now() returns a "naive" datetime with no timezone attached, which Django will complain about (or silently produce times that drift, depending on server location). timezone.now() always returns a timezone-aware datetime matching your project's configured timezone.

# 3. Class Signature — every symbol explained
# python
# class BaseModelAdmin(admin.ModelAdmin):

# class BaseModelAdmin — same as last time: defining a new blueprint, named BaseModelAdmin.

# (admin.ModelAdmin) — inheritance again. This class is a specialized version of Django's ModelAdmin. Everything ModelAdmin already knows how to do (rendering forms, handling list views, permissions checks) is inherited for free. We're only overriding/adding a few specific behaviors.

# Why admin.ModelAdmin and not just ModelAdmin? Because we imported the whole admin module (from django.contrib import admin), not the individual class. So to reach ModelAdmin, we have to go through the module first — admin.ModelAdmin means "the ModelAdmin tool, found inside the admin module." (Contrast this with your last file, where we imported AppConfig directly, so we could write just AppConfig with no prefix.)

# 4. Classes — why this design

# Why a class, not standalone functions? Because Django's admin system expects a specific shape of object — one with certain attributes (list_display, readonly_fields, etc.) and certain overridable methods (get_readonly_fields, get_actions). Functions alone can't bundle data (config attributes) and behavior (methods) together, and can't be "handed" to Django's admin.site.register() the way a class can.

# What is self here referring to? An instance of this admin class, created internally by Django once per registered model. So if you have OrderAdmin(BaseModelAdmin) and ProductAdmin(BaseModelAdmin), Django creates two separate instances — self inside each method refers to "the admin object for this specific model," letting self.model correctly mean Order in one case and Product in the other.

# 5. Class attributes (the "data" part)
# python
# readonly_fields = ["id", "created_at", "updated_at"]
# list_display = ["id", "created_at", "updated_at"]
# date_hierarchy = "created_at"

# readonly_fields = ["id", "created_at", "updated_at"]

# Right side: a list (an ordered collection, written with square brackets [...], containing three strings). Each string is a field name on the model.
# Left side: readonly_fields is a specific attribute name ModelAdmin looks for — Django checks this list and disables editing on any field named here, in the admin's edit form.
# Whole line: "In the admin edit screen, don't let anyone type into the id, created_at, or updated_at fields."
# Why these three specifically? Because they're typically auto-generated — id is assigned by the database, and created_at/updated_at are typically auto-set by the model itself (often via auto_now_add=True / auto_now=True). Letting a human edit them would be meaningless or dangerous — Django would just overwrite whatever they typed anyway.

# list_display = ["id", "created_at", "updated_at"]

# Same list shape, different purpose: this controls which columns show up in the admin's list view (the table showing all rows of this model), not the edit form.
# Whole line: "When showing the table of all records, show columns for id, created date, and updated date."

# date_hierarchy = "created_at"

# Right side: a single string (not a list this time) — the name of one specific date/datetime field.
# Whole line: "Add a drill-down date navigation bar (Year → Month → Day) at the top of the list view, based on created_at."
# 6. get_readonly_fields — line by line
# python
# def get_readonly_fields(self, request, obj=None):
#     fields = super().get_readonly_fields(request, obj)
#     if hasattr(self.model, "deleted_at"):
#         fields = list(fields) + ["deleted_at"]
#     return fields

# Signature first:

# def get_readonly_fields(self, request, obj=None): — this method name is not arbitrary; it's one Django's ModelAdmin already defines, and we're overriding it (replacing Django's version with our own, customized version).
# request — the incoming HTTP request object (who's viewing the page, what permissions they have, etc.). We don't use it directly here, but Django's method signature requires it, and we pass it along.
# obj=None — the specific model instance being edited, if any. =None is a default value: "if nobody's editing a specific object yet (e.g. this is the 'add new' screen), assume there isn't one." This matters because on the "add" screen, there's no object yet to check.

# Line 1: fields = super().get_readonly_fields(request, obj)

# Right side, read left to right: super() means "give me access to the parent class's version of things" — here, the original ModelAdmin.get_readonly_fields method, before our override. Calling .get_readonly_fields(request, obj) on it runs Django's normal logic and returns whatever the parent class would have returned (in our case: your class-level readonly_fields = ["id", "created_at", "updated_at"]).
# Left side: store that result in a local variable, fields.
# Whole line: "Start with whatever the normal Django admin logic would already return as read-only fields."
# Why call super() instead of just referencing self.readonly_fields directly? Because super().get_readonly_fields() runs Django's actual logic, which is smarter than the raw attribute — it also handles cases like fields that are read-only due to permissions. Calling the parent method is safer than duplicating/guessing that logic yourself.

# Line 2: if hasattr(self.model, "deleted_at"):

# hasattr(X, "name") — a Python built-in function meaning "does object X have an attribute called "name"?" Returns True or False.
# self.model — every ModelAdmin instance automatically has .model set to whichever Django model it's managing (e.g. Order, Product).
# Whole line: "If this particular model has a field/attribute called deleted_at..."
# Why check this at all? Because BaseModelAdmin is shared across many different models, and not all of them necessarily support soft-deletion. This check lets the same base class safely adapt: models with deleted_at get the extra read-only field; models without it don't crash or show a nonexistent field.

# Line 3: fields = list(fields) + ["deleted_at"]

# Right side: list(fields) converts whatever fields currently is into an actual Python list (defensive — the parent method might return a tuple, which can't be added to a list directly). Then + ["deleted_at"] concatenates (joins together) that list with a new one-item list containing "deleted_at".
# Left side: overwrite fields with this new, longer list.
# Whole line: "Add deleted_at onto the end of the read-only fields list."
# Why list(fields) + [...] instead of fields.append("deleted_at")? Because .append() modifies a list in place and requires fields to already be a mutable list — but Django's parent method might return an immutable tuple, and tuples don't have .append(). Using list(...) + [...] works regardless of whether fields started as a list or a tuple — it's the safer, more defensive choice.

# Line 4: return fields

# Hands the (possibly modified) list back to whoever called this method — Django itself, when rendering the edit page.

# Whole method, plain English: "Get Django's normal list of read-only fields. If this specific model also supports soft-deletion, additionally lock the deleted_at field from editing. Return the final list."

# 7. get_actions — line by line
# python
# def get_actions(self, request):
#     actions = super().get_actions(request)
#     if hasattr(self.model, "soft_delete"):
#         if "delete_selected" in actions:
#             del actions["delete_selected"]
#         actions["soft_delete_selected"] = (
#             self.soft_delete_selected,
#             "soft_delete_selected",
#             _("Soft delete selected items")
#         )
#     return actions

# This method controls the dropdown of bulk actions you see above the list table in Django admin (e.g. "Delete selected items").

# Line 1: actions = super().get_actions(request)

# Same pattern as before: get Django's default set of available actions first. This comes back as a dictionary — {"action_key": (function, action_key, description), ...} — mapping an internal action name to a 3-piece bundle describing it.

# Line 2: if hasattr(self.model, "soft_delete"):

# Same defensive check as before: only modify behavior for models that actually implement a soft_delete method/attribute.

# Line 3-4:

# python
# if "delete_selected" in actions:
#     del actions["delete_selected"]
# "delete_selected" in actions — checks: does the dictionary actions have a key named "delete_selected"? (This is Django's default hard-delete bulk action.)
# del actions["delete_selected"] — the del keyword removes that key entirely from the dictionary.
# Whole lines: "If Django's normal hard-delete bulk action exists, remove it."
# Why remove it? Because for models with soft-delete support, you don't want admins able to permanently wipe records via the default action — that would defeat the whole purpose of having soft-delete in the first place.
# Why check if "delete_selected" in actions first, instead of just deleting directly? Because deleting a dictionary key that doesn't exist raises a KeyError and crashes. The in check guards against that — defensive programming.

# Lines 5-10:

# python
# actions["soft_delete_selected"] = (
#     self.soft_delete_selected,
#     "soft_delete_selected",
#     _("Soft delete selected items")
# )
# Left side: actions["soft_delete_selected"] = ... — this creates a new key in the dictionary called "soft_delete_selected", with whatever value follows.
# Right side: a tuple (parentheses, immutable, ordered group of exactly 3 items) — this is the exact 3-piece shape Django's admin requires for every action: (the_function_to_run, internal_name, display_label).
# self.soft_delete_selected — a reference to the method defined just below (notice: no parentheses here — we're not calling it yet, we're just handing Django the function itself, to be called later when someone actually picks this action from the dropdown).
# "soft_delete_selected" — the internal string key/name for this action.
# _("Soft delete selected items") — the human-visible label shown in the dropdown, wrapped for translation.
# Whole lines: "Register a new bulk action called 'soft_delete_selected,' which — when chosen — runs self.soft_delete_selected, and displays as 'Soft delete selected items' in the dropdown."

# Line 11: return actions

# Hand back the modified dictionary of available actions.

# Whole method, plain English: "Get Django's default bulk actions. If this model supports soft-deletion, remove the dangerous hard-delete action and replace it with a safe soft-delete action instead."

# 8. soft_delete_selected — the actual action
# python
# def soft_delete_selected(self, request, queryset):
#     queryset.update(is_deleted=True, deleted_at=timezone.now())
# soft_delete_selected.short_description = _("Soft delete selected items")

# Signature: Django's admin action functions have a required shape: (self, request, queryset). queryset here is the specific set of rows the admin user checked the boxes for in the list view — Django hands you exactly those selected records, already filtered.

# Body: queryset.update(is_deleted=True, deleted_at=timezone.now())

# queryset.update(...) — a Django QuerySet method that updates every matching row in the database in one single SQL query (much more efficient than looping through each object and calling .save() individually).
# is_deleted=True — a keyword argument: set the is_deleted field to True for all these rows.
# deleted_at=timezone.now() — set the deleted_at field to the current timezone-aware timestamp.
# Whole line: "For every selected row, mark it as deleted and stamp the current time as when it was deleted — without actually removing the row from the database."

# The last line — outside the method, but still inside the class:

# python
# soft_delete_selected.short_description = _("Soft delete selected items")
# This is unusual to a beginner: it's setting an attribute directly on the function itself, after it's been defined. In Python, functions are objects too — you can attach arbitrary attributes to them, just like you'd attach an attribute to any other object.
# short_description is a special attribute name Django's admin specifically looks for on action functions to determine the dropdown label — this is actually redundant here, since the label was already passed via the tuple in get_actions(). But it's a defensive fallback: if this action were ever registered a different way (e.g. via the simpler actions = [...] list syntax that many other Django admin classes use), Django would fall back to reading this attribute for the label instead.
# 9. Beginner questions, answered proactively

# Why parentheses around the tuple (self.soft_delete_selected, "soft_delete_selected", _(...)) spanning multiple lines?
# Parentheses let you spread one expression across multiple lines for readability, without needing a special line-continuation character. Python understands "we're still inside the same parentheses" and doesn't treat each line as a separate statement.

# Why hasattr() instead of checking isinstance() or importing a specific soft-delete mixin class?
# hasattr() is Python's "duck typing" philosophy: "if it has the attribute I need, I don't care what specific class it is." This keeps BaseModelAdmin flexible — it works for any model that happens to define deleted_at/soft_delete, without needing to know or import those model classes directly (which would create tangled cross-app dependencies).

# Why is queryset.update(...) used instead of looping and calling .save() on each object?
# .update() translates to a single UPDATE ... WHERE ... SQL statement — fast, regardless of how many rows are selected. Looping and calling .save() on each object individually would run one database query per object, which is much slower for large selections, and would also re-trigger any custom .save() logic/signals — which may or may not be desired.

# Why check hasattr(self.model, "deleted_at") in one method but hasattr(self.model, "soft_delete") in another — aren't those the same check?
# Not necessarily — they're checking for two different things that likely go together but aren't guaranteed to: deleted_at is a field (data), soft_delete is presumably a method (behavior) defined on the model. The code assumes any model with one also has the other, but technically they're independent checks, matching whichever specific thing that method actually needs.

# 10. Design discussion

# Why override get_readonly_fields/get_actions instead of just hardcoding readonly_fields = [...] including deleted_at, and a static actions = [...] list?
# Because not every model using BaseModelAdmin has soft-delete support. If deleted_at were hardcoded into the class-level readonly_fields list, Django would crash for any model without that field (you can't mark a nonexistent field as read-only). Overriding the get_* methods lets the class adapt per-model at runtime, only adding soft-delete-specific behavior when it's actually applicable.

# Trade-off: This dynamic, hasattr-based approach is more flexible but slightly harder to statically reason about — you can't just glance at BaseModelAdmin and know "which fields will show up" for a given model; you have to also know whether that model has deleted_at/soft_delete. An alternative design would be a more explicit mixin class (e.g. SoftDeleteAdminMixin) that specific admin classes opt into deliberately — trading a bit of "automatic magic" for more explicit, readable class definitions. Both are valid; this file chose implicit convenience over explicit opt-in.

# 11. DIY Recipe — build your own base admin class
# Identify the fields that are common across most/all of your models (e.g. id, created_at, updated_at) — put them in class-level readonly_fields/list_display.
# Identify optional, model-specific behaviors (e.g. soft-delete) that only some models support.
# For each optional behavior, override the relevant ModelAdmin hook method (get_readonly_fields, get_actions, etc.) rather than hardcoding it.
# Inside the override, always call super().<method>(...) first to preserve Django's normal behavior, then layer your customization on top.
# Guard model-specific logic behind hasattr(self.model, "some_field_or_method") so the base class stays safe to use across models that don't support that feature.
# When adding/removing bulk actions, remember get_actions() returns a dictionary — use in/del safely, and register new actions as (function, name, label) tuples.
# For any action that mutates the database, prefer queryset.update(...) for bulk safety and speed over per-object loops.
# 12. General pattern recognition

# This is the Template Method + Hook Override pattern: a base class provides sensible defaults, and subclasses/overrides customize specific pieces by calling super() and adding to the result, rather than replacing behavior wholesale. You'll see this same shape anywhere Django (or any framework) exposes a method specifically meant to be overridden — DRF serializers overriding to_representation(), Django forms overriding clean(), Django models overriding save().

# The other pattern here: capability checking via hasattr() — "does this object support the feature I need?" instead of "is this object exactly this class?" You'll see this same defensive style anywhere code needs to work across a variety of model types that don't all share a common ancestor class.

# 13. Real project usage

# Given your project's conventions (soft-delete-aware models, require_owner()/require_permission()), this BaseModelAdmin is almost certainly meant to be the parent class for admin registrations across rbac.accounts, rbac.staff, rbac.products, rbac.orders, etc. — anywhere: class OrderAdmin(BaseModelAdmin): ..., then admin.site.register(Order, OrderAdmin).

# 14. Common beginner mistakes
# ❌ Forgetting to call super() in an overridden method — this silently throws away Django's default behavior instead of building on it.
# ❌ Calling .append() on whatever super() returns, without converting to a list first — crashes if Django returns a tuple.
# ❌ Deleting a dictionary key without checking in first — raises KeyError.
# ❌ Using self.model.deleted_at directly instead of hasattr(self.model, "deleted_at") — this would actually try to access the attribute (which may not exist at all on the class, or behave unexpectedly), rather than just checking for it.
# ❌ Writing self.soft_delete_selected() with parentheses inside the actions tuple — that would call the method immediately (at class-definition time) instead of handing Django a reference to call later, and would crash since it's missing the required request/queryset arguments.
# ❌ Looping with .save() instead of queryset.update() for bulk actions — needlessly slow at scale.
# 15. Think like the original developer
# "I have many models across many apps. Most share the same boilerplate admin config — I should write that once."
# "Some models additionally support soft-delete. I can't assume all of them do, so I need a check, not a hardcoded assumption."
# "Django's admin already has a hook for 'what fields are read-only' and 'what actions exist' — I should tap into those hooks rather than reinvent admin rendering myself."
# "Whatever I add should extend Django's normal behavior, not replace it — so I always start from super()'s result."
# "If a model has soft-delete, the dangerous default hard-delete action should be swapped out for a safe equivalent — otherwise I've built the feature but left a footgun sitting right next to it."
# "The safest and fastest way to bulk-modify selected rows is a single .update() call, not per-row saves."

# That chain of reasoning — "share common config, detect optional capabilities, extend rather than replace, guard against unsafe defaults" — is this file.