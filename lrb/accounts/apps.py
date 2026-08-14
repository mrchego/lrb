from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "lrb.accounts"
    label = "accounts"
    verbose_name = _("Accounts")

    def ready(self):
        pass
    
# core/apps.py — Django AppConfig
# 1. Purpose — What problem does this solve?

# Django is built from many small "apps" (accounts, identity, staff, orders, etc. — you have a whole list of these). Django needs a way to:

# Know that a folder like lrb/core/ is actually a Django app, not just a random Python folder
# Let that app register itself, configure settings, and run setup code exactly once when the project starts
# Give that app a human-readable name to show in Django's admin site

# Why not just skip this file? Django could guess app names from folder names, but guessing breaks down fast — folder names might collide, translations wouldn't work, and there'd be no hook to run startup code (like registering signal handlers). So Django requires every app to have a small "config" class describing itself.

# When is this used? The moment your Django project boots up (runserver, manage.py, Docker container starting), Django reads INSTALLED_APPS in your settings, finds "lrb.core" listed there, walks into that app's apps.py, and loads this CoreConfig class to learn about the app.

# What breaks without it? Technically Django can auto-generate a default config if you don't write one. But then you lose: a translatable display name, a stable "label" (used internally as a namespace for models), and — critically — the ready() hook, which is where apps commonly register signals (e.g. "when a User is created, also create a Profile"). Without a custom config, you have nowhere reliable to put that startup logic.

# 2. Imports — explained like you've never programmed
# python
# from django.apps import AppConfig
# from django.utils.translation import gettext_lazy as _

# import — a command that tells Python "go get code that already exists somewhere else, and let me use it here." Without imports, every file would have to reinvent everything from scratch.

# from X import Y — this says "go into the module X, and pull out just the piece named Y, don't bring the whole thing." It's like saying "from the toolbox, hand me just the screwdriver" instead of carrying the whole toolbox.

# django — this is a third-party package (not built into Python itself). It's the web framework your whole project is built on. It was written by the Django Software Foundation, not by you, not by Python's creators. You installed it (via pip install django), and now your code can use it.

# django.apps — the dot here means "go inside the django package, then into its apps sub-module." Think of django as a filing cabinet with drawers, and .apps is one specific drawer. That drawer contains tools related to app configuration.

# AppConfig — the specific tool (a class) we're pulling from that drawer. It's the base blueprint Django provides for "describing an app." We don't write app-config logic from zero; we borrow Django's blueprint and customize it.

# django.utils.translation — another drawer, this one containing tools for translating text into different languages.

# gettext_lazy as _ — gettext_lazy is a function whose job is "mark this string as translatable, but don't actually translate it right now — wait until it's actually displayed." The as _ part renames it to just _ while importing. This is a very common Django/Python convention — _ is used purely as a short alias so you don't have to type gettext_lazy(...) everywhere.

# Could you write your own package like django? Yes — technically django is just Python code, organized into folders and files, published so others can pip install it. There's nothing magical separating "packages someone else wrote" from "packages you could write" — it's the same language, just already built and shared.

# Why import only AppConfig, not everything in django.apps? Because pulling in only what you need keeps things clear and avoids accidentally overwriting names you didn't mean to import. If django.apps has 10 tools and you only need 1, grabbing just that 1 keeps your file's imports honest about what it actually uses.

# 3. Class Signature — every symbol explained
# python
# class CoreConfig(AppConfig):

# class — a keyword meaning "I'm about to define a new blueprint/category of object," as opposed to def, which defines a reusable action. A class defines a reusable thing.

# CoreConfig — the name we're giving this blueprint. By Django convention, app config classes are named <AppName>Config.

# (AppConfig) — this is inheritance. It means "CoreConfig is a specialized version of AppConfig." Django's AppConfig already knows how to do 90% of the work (registering the app, exposing default settings, etc.). We don't rewrite that — we inherit it, and only override the small parts specific to this app.

# Why parentheses here, if this isn't a function call? Parentheses are reused in Python for more than one purpose. On a class line specifically, they mean "this new class is built on top of / inherits from what's inside the parentheses" — not "call this with an argument."

# : — marks "everything indented below this line belongs to the class block." Python doesn't use { } curly braces like some languages; indentation is the grouping mechanism.

# 4. The class body — attributes explained one at a time
# python
# default_auto_field = "django.db.models.BigAutoField"
# name = "lrb.core"
# label = "core"
# verbose_name = _("Core")

# These four lines are class attributes — plain variables that live directly on the class, not inside a function. Think of them as a settings form Django reads.

# default_auto_field = "django.db.models.BigAutoField"

# Right side: the string "django.db.models.BigAutoField" — this tells Django which kind of automatic ID field to use for any model in this app that doesn't explicitly define its own primary key. BigAutoField is a large auto-incrementing integer (bigger range than the older default AutoField), which matters if a table might someday hold billions of rows.
# Left side: default_auto_field is the specific attribute name Django looks for. You don't choose this name — it's part of AppConfig's contract. Django will literally check self.default_auto_field internally.
# Whole line, plain English: "For every model in this app that doesn't specify its own ID type, use a big auto-incrementing integer."

# name = "lrb.core"

# This is the required, most important line in the whole file. It's the Python import path to this app — literally where Python would find it if you wrote import lrb.core.
# This must exactly match the app's real location, and it must exactly match what's listed in INSTALLED_APPS in your settings file. This is how Django connects "the string in settings" to "this specific config class."
# Plain English: "This config describes the app that lives at lrb.core."

# label = "core"

# A short internal nickname for the app, used as a namespace prefix. For example, database table names default to <label>_<modelname> (e.g. core_somemodel), and Django's admin/migrations refer to apps by their label.
# Why have both name (full path) and label (short nickname)? Because name can be long and nested (lrb.core), but label needs to be short, unique, and valid as an identifier (no dots). Django auto-generates a label from name if you don't set one (it would default to core here anyway, using the last segment) — but setting it explicitly makes it stable and intentional, protecting you if you ever move/rename the folder.

# verbose_name = _("Core")

# Right side, read left to right: _(...) calls the gettext_lazy function we imported (aliased as _), passing it the string "Core". This wraps "Core" so that, when displayed to a user, Django can swap in a translated version depending on the user's language settings — but only translates it lazily, at display time, not immediately at import time (important because translations aren't ready yet when Python first loads this file).
# This is purely cosmetic/human-facing — it's the label an admin sees in the Django admin site's sidebar (e.g. "Core" as a section heading), as opposed to name/label, which are internal machine identifiers.
# Whole line: "The human-readable display name for this app is 'Core,' and make it translatable."
# python
# def ready(self):
#     pass

# def — "I'm defining a reusable action" (a method, since it's inside a class).

# ready — the method name. This name is not arbitrary — AppConfig defines ready() as a hook: Django automatically calls this method once, after all apps and their models have finished loading. You're overriding a method that already exists on the parent class.

# (self) — self refers to "this specific instance of the class calling the method" — i.e., "this particular app's config object." Every method inside a class needs self as its first parameter so the method can access the object's own attributes (like self.name).

# : — again, marks the start of the indented block belonging to this method.

# pass — a Python keyword meaning "do nothing, but this block still needs something here because Python doesn't allow an empty block." It's a placeholder. Right now, ready() does literally nothing beyond what Django already does by default.

# Whole method, plain English: "When Django finishes loading all apps, call this method on the Core app — but for now, don't do anything extra."

# 5. Beginner questions, answered proactively

# Why does ready() exist if it just does nothing?
# Because it's commonly needed later. The most typical use is importing your signal handlers here, e.g. from . import signals. Signals must be imported somewhere so Python actually registers them, and ready() is the officially correct place — importing them at the top of the file (module level) can cause circular-import errors, since models might not be loaded yet.

# Why not just remove ready() entirely if it's empty?
# You could — AppConfig would just use its own default (also does nothing). Leaving it here, empty, is often intentional scaffolding: a placeholder that says "this is where startup logic will go later," so the next developer knows exactly where to add it.

# Why indentation instead of braces?
# Python enforces readability by making indentation mean something structurally, not just look nice. It removes the ambiguity of "which } closes which {" you get in other languages.

# Why = "core" as a plain string instead of some special Django "Label" object?
# Django keeps this simple on purpose — labels/names are just used as strings internally (for dict keys, DB prefixes, Python import paths), so there's no need for a wrapper object.

# 6. Design discussion — why built this way, not another way?
# Why inherit from AppConfig instead of writing config from scratch? Django's app-loading system (INSTALLED_APPS processing, model registry, migrations) all expects an object shaped like AppConfig. Inheriting guarantees compatibility with all of that machinery for free — reinventing it would mean re-implementing Django's internal app registry.
# Why a class instead of a plain dictionary of settings? A class lets Django call methods on it (like ready()) — a dictionary can't run code. Classes give you both data (name, label) and behavior (hooks) in one object.
# Trade-off of BigAutoField vs the older default AutoField: BigAutoField uses more storage per row (8 bytes vs 4), but avoids ever running out of IDs on a high-growth table. For a learning project this barely matters, but it's Django's modern recommended default since Django 3.2+.
# 7. DIY Recipe — build your own AppConfig from scratch
# Pick the app's Python import path (matches its folder location) → this becomes name.
# Pick a short, unique, dot-free nickname → this becomes label (or just let Django infer it).
# Pick a human-facing display name, wrap it in _() if your project supports multiple languages → this becomes verbose_name.
# Decide the default primary-key field type for models in this app (usually just copy whatever your project standard is) → default_auto_field.
# If this app needs to run setup code once Django is fully loaded (register signals, warm a cache, validate config) → put that code inside ready(self). If nothing's needed yet, leave pass.
# Go to your project's settings.py, find INSTALLED_APPS, and make sure the app is listed there (usually as "lrb.core", or as "lrb.core.apps.CoreConfig" if you want to be explicit about which config class to use).

# This exact recipe applies to every app in your project — accounts, identity, staff, authorization, etc. all have their own nearly-identical apps.py.

# 8. General pattern recognition

# This file follows a pattern you'll see constantly in Django and other frameworks: the "descriptor class." A small class whose entire job is to describe metadata about something else (here: an app) rather than do heavy logic itself. You'll recognize this same shape in:

# Django's Meta classes inside models (class Meta: ordering = [...])
# DRF Serializer Meta classes
# Django admin's ModelAdmin classes

# The tell-tale signs of this pattern: mostly class-level attributes (not methods), one or two optional hook methods, and it exists purely to plug into a larger framework's registry.

# 9. Real project usage

# In your RBAC project, every app you listed — rbac.core, rbac.accounts, rbac.identity, rbac.company, rbac.staff, rbac.authorization, rbac.products, rbac.categories, rbac.orders — has (or should have) a file exactly like this one. The core app specifically is often the place where truly shared, cross-cutting code lives (base models, shared utilities, shared permissions logic) — things every other app might import from, but that don't belong to any single domain app.

# (Side note: your file says lrb.core, but your project notes describe the apps as rbac.core, rbac.accounts, etc. — worth double-checking that name actually matches your real import path, since a mismatch here is a classic source of ImproperlyConfigured errors at startup.)

# 10. Common beginner mistakes with apps.py
# ❌ Setting name to just "core" instead of the full dotted path "lrb.core" — Django needs the importable path.
# ❌ Forgetting to add the app (or its config class) to INSTALLED_APPS — the class existing isn't enough; Django has to be told to load it.
# ❌ Putting signal-registration import statements at the top of the file instead of inside ready() — causes circular import errors because models aren't ready yet.
# ❌ Manually hardcoding label in a way that collides with another app's label — labels must be unique project-wide.
# ❌ Forgetting _() around verbose_name in projects that need translations, then wondering why admin text never changes with the language setting.
# 11. Think like the original developer

# If you had no reference and had to invent this yourself, here's the reasoning chain:

# "My project has multiple independent chunks of functionality (apps). Django needs to discover and load each one."
# "Each app needs a name Django can use to find it — that has to be the real Python import path."
# "Each app needs a short internal nickname for database prefixes and internal bookkeeping — separate from the long path, so it's not so unwieldy."
# "Someone will look at the Django admin someday — that person needs a friendly label, not a Python identifier. And if this project ever supports other languages, that label needs to be translatable."
# "New models in this app need some default primary key strategy — I should declare it explicitly rather than rely on defaults that might silently change between Django versions."
# "Sometimes an app needs to run code exactly once, after everything is loaded — I need one designated method for that, so it doesn't run twice or run too early."
# "The cleanest way to package all of this together — data plus a lifecycle hook — is a class, inheriting from whatever base class the framework already provides for this exact purpose."

# That reasoning chain, followed step by step, is Django's AppConfig design.

# Quick line-by-line reading walkthrough (applying your "read by meaning" method)
# python
# default_auto_field = "django.db.models.BigAutoField"
# Pattern: simple assignment → read the right side first.
# Right side: the string naming a specific field class.
# Left side: the attribute name Django checks for.
# Sentence: "Set this app's default primary-key field type to BigAutoField."
# python
# verbose_name = _("Core")
# Pattern: function call, nested inside an assignment → evaluate the call first.
# Inner call: _("Core") → verb: mark-for-translation; input: "Core".
# Then assign the result to verbose_name.
# Sentence: "Wrap 'Core' as a translatable string, and use that as this app's display name."