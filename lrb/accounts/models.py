from django.db import models
from typing import ClassVar
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _
from lrb.core.models.base import BaseModel
from lrb.accounts.managers import UserManager
from lrb.core.utilis.files import avatar_upload_path
from lrb.core.validators.phone import validate_phone_number


class User(BaseModel, AbstractUser):
    username = None
    name = None

    email = models.EmailField(_("Email Address"), unique=True)
    is_email_verified = models.BooleanField(
        default=False,
        help_text=_("Whether the user has confirmed ownership of their email address."),
    )
    first_name = models.CharField(_("First Name"), max_length=100, blank=True)
    last_name = models.CharField(_("Last Name"), max_length=100, blank=True)
    phone = models.CharField(
        _("Phone Number"), max_length=20, blank=True, validators=[validate_phone_number]
    )
    avatar = models.ImageField(upload_to=avatar_upload_path, blank=True, null=True)
    is_founder = models.BooleanField(
        default=False,
        help_text=_(
            "The user who originally registered the company. Founders cannot be "
            "deactivated, locked, deleted, or demoted from ownership by anyone, "
            "including other owners."
        ),
    )
    
    company = models.ForeignKey("company.Company", on_delete=models.CASCADE, related_name="users", null=True, blank=True)
    
    can_login = models.BooleanField(default=True, help_text=_("Determines whether the user can sign in"))
    password_reset_required = models.BooleanField(default=False)
    last_password_change = models.DateTimeField(null=True, blank=True)
    failed_login_attempts = models.PositiveIntegerField(default=0)
    locked_until = models.DateTimeField(null=True, blank=True)
    
    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []
    
    objects: ClassVar[UserManager] = UserManager()
    
    class Meta:
        ordering = ["-created_at"]
        verbose_name = _("User")
        verbose_name_plural = _("Users")
        
        indexes = [
            models.Index(fields=["company"]),
            models.Index(fields=["is_active"]),
            models.Index(fields=["can_login"])
        ]
        
    @property
    def full_name(self) -> str:
        return " ".join(part for part in [self.first_name, self.last_name] if part)
    
    @property
    def display_name(self) -> str:
        return self.full_name or self.email
    
    @property
    def is_locked(self) -> bool:
        from django.utils import timezone 
        
        return self.locked_until is not None and self.locked_until > timezone.now()
    
    def __str__(self) -> str:
        return self.display_name
    
# 1. Purpose — What problem does this solve?

# Every Django project needs some representation of "a person who can log in." Django ships a default User model, but it's deliberately generic — username-based login, no company association, no lockout tracking, no avatar, etc. Real projects almost always need to customize it.

# This file defines your actual User — the central identity in your entire RBAC system. Every permission check (require_owner(), require_permission()), every "who created this record," every login — all of it ultimately points back to an instance of this class.

# Why not just use Django's default User as-is? Because your project needs things Django's default doesn't have: email-only login (no username), company membership (multi-tenant RBAC — "which company does this user belong to?"), account lockout after failed logins, a founder flag with special un-removable protections, avatar uploads, phone validation, and password-reset-required tracking. None of that exists in Django's stock model.

# Why not build a completely separate model instead of extending Django's? Because Django's authentication system (login(), logout(), permission checks, session handling, the admin site) is deeply wired to expect something shaped like Django's AbstractUser/AbstractBaseUser. Extending it means you get all of that machinery for free, and only override the parts that differ.

# What breaks without it? Without a custom User, you'd be stuck with username-based login (contradicting your project's email-based auth), no way to associate users with companies (breaking your entire multi-tenant RBAC design), and no lockout/security fields.

# 2. Imports — explained like you've never programmed
# python
# from django.db import models
# from typing import ClassVar
# from django.contrib.auth.models import AbstractUser, UserManager
# from django.utils.translation import gettext_lazy as _
# from lrb.core.models.base import BaseModel
# from lrb.accounts.managers import UserManager
# from lrb.core.utilis.files import avatar_upload_path
# from lrb.core.validators.phone import validate_phone_number

# django.db — the part of Django responsible for talking to the database. models — inside it, the module containing all the building blocks for defining database tables as Python classes: models.Model, models.CharField, models.EmailField, models.ForeignKey, etc. You'll use models.X constantly in this file.

# typing / ClassVar — typing is Python's built-in type-hinting toolkit (you saw TYPE_CHECKING from it last file). ClassVar is a specific hint meaning "this attribute belongs to the class itself, not to individual instances" — you'll see exactly where this matters below.

# django.contrib.auth.models → AbstractUser, UserManager — Django's authentication app. AbstractUser is Django's own abstract base class (a template you're meant to extend, not use directly) containing most of the standard user fields and login behavior. UserManager here is Django's default manager — imported, but about to be shadowed (more on this below).

# django.utils.translation → gettext_lazy as _ — the same translation tool from every previous file.

# lrb.core.models.base → BaseModel — this is almost certainly the shared base class providing id, created_at, updated_at — the same fields your BaseModelAdmin file assumed every model would have (readonly_fields = ["id", "created_at", "updated_at"]). This is where those fields actually get defined.

# lrb.accounts.managers → UserManager — this is your own custom manager, the exact file you just finished reading in the previous turn.

# lrb.core.utilis.files → avatar_upload_path — a function (defined elsewhere) that decides where on disk/storage an uploaded avatar image should be saved. (Small side note, not urgent: utilis looks like it might be a typo for utils — worth a quick check in your actual codebase so imports stay consistent project-wide.)

# lrb.core.validators.phone → validate_phone_number — a custom validator function, structurally identical in spirit to validate_password_strength from two files ago — just checking phone number format instead of password length.

# ⚠️ Something worth stopping on: the double UserManager import
# python
# from django.contrib.auth.models import AbstractUser, UserManager
# ...
# from lrb.accounts.managers import UserManager

# Both lines import something named UserManager into this file. In Python, when you import the same name twice, the second import silently overwrites the first in this file's namespace. So by the time you reach the bottom of the file and write objects: ClassVar[UserManager] = UserManager(), the name UserManager refers only to your custom one from lrb.accounts.managers — Django's own UserManager import is completely shadowed and effectively unused.

# This isn't necessarily broken — you clearly intend to use your custom manager — but it's worth knowing precisely why it works: not because Python is smart enough to know which one you meant, but because the second import silently replaces the first, and nothing on this line is dependent on Django's original UserManager being separately accessible. Most linters (ruff, flake8) would actually flag AbstractUser, UserManager on that first import line as "imported but unused," since UserManager there is never referenced under that name before being overwritten. You may want to import UserManager only from lrb.accounts.managers, and drop it from the django.contrib.auth.models import line, to keep intent unambiguous.

# 3. Class Signature — every symbol explained
# python
# class User(BaseModel, AbstractUser):

# class User — defining the class, matching USERNAME_FIELD/Django convention that this is the user model.

# (BaseModel, AbstractUser) — multiple inheritance: this class inherits from two parent classes at once, separated by a comma. This is new — every previous file you've read only inherited from one parent.

# What does inheriting from two classes actually mean? User gets all the fields and methods from BaseModel (presumably id, created_at, updated_at, and maybe soft-delete fields) and all the fields/methods from AbstractUser (Django's password, is_active, is_staff, permissions/groups relationships, check_password(), etc.) — combined into one class.

# Why does the order (BaseModel, AbstractUser) matter? Python resolves multiple inheritance left-to-right using something called the Method Resolution Order (MRO) — when both parents define something with the same name, the one listed first generally takes priority. Listing BaseModel first signals "my own project's base conventions take precedence over Django's defaults where they conflict." For pure database fields (as opposed to methods), Django's model system merges fields from all parents rather than truly "overriding" in the MRO sense — but for methods and Meta inheritance behavior, order does matter.

# 4. The body — field by field

# Django model fields all follow one recurring shape: field_name = models.SomeFieldType(options...). Each field becomes one column in the database's User table.

# python
# username = None
# name = None
# AbstractUser normally defines a username field (and some Django user-mixins define a name field). Setting them to None here removes those inherited fields from your model entirely — Django specifically recognizes field = None on a subclass as "delete this inherited field, don't create this column."
# Whole lines: "This model does not use username or name — I'm opting out of Django's default identifier field entirely," which matches USERNAME_FIELD = "email" further down.
# python
# email = models.EmailField(_("Email Address"), unique=True)
# models.EmailField(...) — a specific field type for storing/validating email-formatted text.
# First argument, _("Email Address") — this is the field's verbose name (human-readable label shown in forms/admin), passed positionally (not as a keyword) — this is simply how Django field constructors accept the label as their first positional argument.
# unique=True — a keyword argument telling the database "no two rows may have the same value in this column" — enforced at the database level, not just in Python. This is what makes email usable as a login identifier: it has to be unambiguous.
# Whole line: "Every user has a unique email address, labeled 'Email Address' in forms."
# python
# is_email_verified = models.BooleanField(
#     default=False,
#     help_text=_("Whether the user has confirmed ownership of their email address."),
# )
# models.BooleanField — stores True/False.
# default=False — if not explicitly set when creating a user, assume unverified.
# help_text=_(...) — descriptive text shown below the field in forms/admin (different from the label — this is explanatory guidance, not the field's name).
# Whole line: "Track whether this user has proven they own their email; default to 'not yet verified.'"
# python
# first_name = models.CharField(_("First Name"), max_length=100, blank=True)
# last_name = models.CharField(_("Last Name"), max_length=100, blank=True)
# models.CharField — stores short text, and (unlike most field types) requires max_length — the database needs to know how many characters to reserve.
# blank=True — this specifically controls form validation: "this field is allowed to be left empty in forms." (Contrast with null=True, which controls the database — allowed to store NULL. CharField conventionally uses blank=True alone, storing empty string "" rather than NULL, to avoid having two different "no value" states — NULL and "" — for text fields.)
# Whole lines: "First and last name are optional text fields, up to 100 characters."
# python
# phone = models.CharField(
#     _("Phone Number"), max_length=20, blank=True, validators=[validate_phone_number]
# )
# Same CharField shape as above, plus: validators=[validate_phone_number] — a list containing your custom validator function (the same kind of function as validate_password_strength from two files back). Django automatically calls every function in this list whenever the field is validated (e.g., via a form or full_clean()), raising ValidationError if the phone number is malformed.
# Whole line: "An optional phone number field, validated against your custom phone-format rule."
# python
# avatar = models.ImageField(upload_to=avatar_upload_path, blank=True, null=True)
# models.ImageField — stores an uploaded image file (a specialized FileField that also validates it's actually a valid image).
# upload_to=avatar_upload_path — instead of a fixed folder string, this passes a function reference (no parentheses — same "hand over the function itself, don't call it yet" pattern you saw with self.soft_delete_selected in the admin file). Django will call avatar_upload_path(instance, filename) itself, at upload time, to dynamically compute where this specific user's avatar should be stored (commonly used to namespace uploads per-user, e.g. avatars/user_42/photo.jpg).
# blank=True, null=True — both this time, because ImageField is a file field, not text: an empty file reference is genuinely represented as NULL in the database (there's no meaningful "empty string" equivalent for "no file").
# Whole line: "An optional avatar image, stored at a path computed dynamically per-user."
# python
# is_founder = models.BooleanField(
#     default=False,
#     help_text=_(
#         "The user who originally registered the company. Founders cannot be "
#         "deactivated, locked, deleted, or demoted from ownership by anyone, "
#         "including other owners."
#     ),
# )
# Same BooleanField shape as is_email_verified. The help_text here spans multiple lines using adjacent string literals — Python automatically joins consecutive quoted strings sitting next to each other into one combined string, purely for code readability (no + needed).
# Whole line, and what it tells you architecturally: this is a special, protected role — your RBAC system apparently has a rule (enforced elsewhere, likely in a service function, since a help_text comment alone can't enforce behavior) that founders are immune to demotion/removal, even by other owners.
# python
# company = models.ForeignKey("company.Company", on_delete=models.CASCADE, related_name="users", null=True, blank=True)
# models.ForeignKey(...) — defines a relationship to another model — "this user belongs to (at most) one company."
# "company.Company" — the related model, written as a string "app_label.ModelName" instead of importing the actual Company class directly. This avoids a circular import (same reasoning as the TYPE_CHECKING trick from the manager file) — company/models.py might itself need to reference User somehow, so referring to Company by string here avoids both files needing to fully import each other at load time.
# on_delete=models.CASCADE — tells Django what to do to this user row if the related Company row is deleted: CASCADE means "delete this user too." (Other options exist, like SET_NULL or PROTECT — CASCADE was chosen here, meaning company deletion takes its users with it.)
# related_name="users" — lets you query backwards from a Company instance: some_company.users.all() — without this, Django would generate a clunkier default name.
# null=True, blank=True — a user can exist without belonging to any company (both database-NULL-allowed and form-optional).
# Whole line: "Each user optionally belongs to one company; if that company is deleted, delete this user too; access a company's users via company.users."
# python
# can_login = models.BooleanField(default=True, help_text=_("Determines whether the user can sign in"))
# password_reset_required = models.BooleanField(default=False)
# last_password_change = models.DateTimeField(null=True, blank=True)
# failed_login_attempts = models.PositiveIntegerField(default=0)
# locked_until = models.DateTimeField(null=True, blank=True)
# These five fields together implement account security/lockout tracking — a common RBAC/security pattern:
# can_login — a manual kill-switch separate from Django's own is_active (inherited from AbstractUser) — likely lets an admin disable sign-in without fully deactivating the account record.
# password_reset_required — forces a user to change their password on next login (e.g., after an admin-initiated reset).
# last_password_change — audit trail of when the password last changed.
# failed_login_attempts — a counter, using PositiveIntegerField specifically (can't go negative — matches its real-world meaning; a count can't be -1), presumably incremented by login logic elsewhere and used to trigger lockout.
# locked_until — a DateTimeField, null=True (no lockout by default) — used together with the is_locked property you'll see below.
# 5. USERNAME_FIELD / REQUIRED_FIELDS — Django's special contract
# python
# USERNAME_FIELD = "email"
# REQUIRED_FIELDS = []

# These aren't ordinary fields — they're class attributes with special meaning that Django's authentication system specifically looks for by these exact names.

# USERNAME_FIELD = "email" — tells Django's entire auth system (login forms, authenticate(), createsuperuser, admin login) "the field that uniquely identifies a user for login purposes is email, not the default username." This is the single line that fundamentally makes your project email-based.
# REQUIRED_FIELDS = [] — a list of additional fields (beyond USERNAME_FIELD and password) that createsuperuser will interactively prompt for. An empty list means: only email and password are required to bootstrap a superuser — nothing else.
# 6. objects: ClassVar[UserManager] = UserManager()

# This line does two different things at once — a type annotation, and an actual assignment.

# Right side (the actual runtime behavior): UserManager() — this calls your custom manager class (from the previous file) to construct an instance, and assigns it to objects. This is the exact line that connects your _create_user/create_user/create_superuser manager logic to this model — from now on, User.objects.create_user(...) calls straight into that manager.
# Left side type hint, objects: ClassVar[UserManager] — ClassVar (imported earlier) tells type-checking tools "objects is an attribute of the class User itself, not something that varies per individual user instance." This matters because, without the hint, some type checkers might assume objects could be a per-instance attribute (like self.email), which would be conceptually wrong — there's exactly one manager shared by the whole model, not one per row.
# Why objects as the name specifically? By Django convention, objects is the default manager name Django's own tooling (admin, .filter() shortcuts, etc.) expects to find on a model, unless told otherwise. Using this exact name keeps everything else in Django working normally.
# 7. The Meta class
# python
# class Meta:
#     ordering = ["-created_at"]
#     verbose_name = _("User")
#     verbose_name_plural = _("Users")
    
#     indexes = [
#         models.Index(fields=["company"]),
#         models.Index(fields=["is_active"]),
#         models.Index(fields=["can_login"])
#     ]

# This is the descriptor-class pattern you already recognized in your first file (CoreConfig)! A nested class Meta: inside a model is Django's standard way of attaching configuration about the model itself (not a field, not a method) — without needing those config options to become actual database columns.

# ordering = ["-created_at"] — whenever you query User.objects.all() without specifying an explicit order, sort by created_at descending (the leading - means descending; no - would mean ascending). So newest users come first by default.
# verbose_name / verbose_name_plural — human-readable singular/plural names, shown in the Django admin ("User" / "Users" instead of Django's auto-generated guess).
# indexes = [...] — a list of database indexes: extra data structures the database maintains to make certain lookups faster. models.Index(fields=["company"]) tells the database "optimize lookups that filter by company" — sensible here, since a multi-tenant RBAC system will constantly run queries like "give me all users in company X." Same reasoning for indexing is_active and can_login — both are almost certainly filtered on very frequently (e.g., "show only active, login-enabled users").

# Why index these three specific fields and not, say, email? email already has unique=True — and in virtually every database, a unique constraint automatically creates an index behind the scenes (needed to efficiently enforce uniqueness). So email is already indexed implicitly; these three are additional, deliberately-chosen indexes for other frequently-filtered fields.

# 8. The @property methods
# python
# @property
# def full_name(self) -> str:
#     return " ".join(part for part in [self.first_name, self.last_name] if part)

# @property — this is new: a decorator (a @-prefixed marker placed directly above a method) that changes how the method is accessed. Normally you'd call a method with parentheses: user.full_name(). @property makes it so you access it like a plain attribute, with no parentheses: user.full_name. Behind the scenes it's still running your code every time it's accessed — @property just changes the syntax for calling it, making computed values look and feel like simple stored data to whoever's using them.

# Why use @property instead of a regular field storing the full name? Because full_name isn't independent data — it's derived from first_name and last_name, which already exist as real fields. Storing it separately would mean two sources of truth that could drift out of sync (e.g., if someone updates first_name but forgets to also update a separately-stored full_name). A @property computes it fresh every time, guaranteeing it's always accurate.

# Body: " ".join(part for part in [self.first_name, self.last_name] if part)

# Reading inside-out: [self.first_name, self.last_name] — a list containing both name fields.
# part for part in [...] if part — this is a generator expression (a compact loop): "for each part in that list, keep it only if part is truthy" (i.e., non-empty — filters out blank first/last names).
# " ".join(...) — takes whatever survived the filter and joins them together with a single space between each.
# Whole line: "Combine first and last name with a space between them, but skip either one if it's blank — so a user with no last name doesn't end up with a trailing space."
# python
# @property
# def display_name(self) -> str:
#     return self.full_name or self.email
# self.full_name — this calls the other property you just read (accessed without parentheses, exactly as designed).
# X or Y — Python's or returns the first "truthy" operand; if full_name ends up being an empty string (both first/last name blank), an empty string is falsy, so this falls through to self.email instead.
# Whole line: "Show the user's full name if they have one set; otherwise fall back to showing their email."
# python
# @property
# def is_locked(self) -> bool:
#     from django.utils import timezone 
    
#     return self.locked_until is not None and self.locked_until > timezone.now()
# Notice: the import statement is inside the method body, not at the top of the file — a local import. This is intentional and common practice for avoiding circular imports or minimizing startup-time imports for rarely-used dependencies — though here, since timezone has no obvious circular-import risk with User, it's more likely just a stylistic/historical choice (possibly moved here to avoid an unused-import warning if timezone isn't used elsewhere in the file).
# self.locked_until is not None and ... — first checks there even is a lockout timestamp set at all (remember, locked_until is null=True — often None).
# and self.locked_until > timezone.now() — Python's and only evaluates the second condition if the first is True (short-circuit evaluation) — so this safely avoids comparing None > timezone.now() (which would crash) when there's no lockout set.
# Whole line: "The user is locked if a lockout timestamp exists and that timestamp is still in the future."
# 9. __str__
# python
# def __str__(self) -> str:
#     return self.display_name
# __str__ — a dunder (double-underscore) method — one of Python's special, framework-recognized method names. This one specifically controls what shows up when a User object is converted to text — e.g., printed, or displayed as the label in Django admin dropdowns/lists.
# Body: reuses the display_name property you just read.
# Whole method: "Whenever this user needs to be shown as text anywhere, show their display name (full name, or email as fallback)."
# 10. Beginner questions, answered proactively

# Why field = None to remove username/name, instead of just not mentioning them? Because they're inherited from AbstractUser (or another mixin) — they already exist unless explicitly removed. Simply "not mentioning" them wouldn't un-define something a parent class already defined; you have to actively override with None.

# Why do some fields use blank=True alone, and others use both blank=True, null=True? Text-based fields (CharField, EmailField) conventionally use blank=True only, storing an empty string "" for "no value" — avoiding two different "empty" representations. Non-text fields (ImageField, DateTimeField, ForeignKey) genuinely need NULL at the database level to represent "nothing here," since there's no equivalent "empty" version of a date or a file reference — so they use both.

# Why is Meta a class instead of just plain attributes directly on User? Namespacing — it clearly separates "configuration about this model" (ordering, display names, indexes) from "actual data fields on this model" (email, phone, etc.). If ordering were just User.ordering = [...], Python (and any developer reading the code) couldn't easily tell it apart from a real field.

# Why do full_name/display_name/is_locked use @property instead of being regular methods you'd call with ()? Because conceptually, from the caller's perspective, these feel like simple facts about the user ("what is their locked status," "what is their display name") rather than actions being performed. @property lets the code reflect that: user.is_locked, not user.is_locked().

# 11. Design discussion

# Why multiple inheritance (BaseModel, AbstractUser) instead of copying id/created_at/updated_at fields directly into this file? Consistency and DRY (don't repeat yourself) — every model in your project presumably inherits BaseModel the same way, so User follows the exact same convention as Order, Product, etc., rather than being a special case that manually redefines shared fields.

# Why put lockout logic (is_locked) as a property here, rather than a service function? This is a genuinely reasonable design question given your project's strict service/selector separation convention. The distinction usually drawn: simple, pure derivations of the model's own existing fields (no database queries, no side effects, no external dependencies) are commonly left as model properties — they're really just convenient read syntax over data the model already has. Actual business operations (checking permissions against other models, incrementing failed_login_attempts, actually locking an account) belong in services. is_locked reads as the former — pure computation from two fields already on self.

# Trade-off of the company = ForeignKey(..., null=True, blank=True) design: Making company membership optional is flexible (supports pre-company-signup users, or platform-level superusers unaffiliated with any company), but it also means every place in the codebase that assumes user.company exists must defensively handle the None case — worth being deliberate about wherever this field is used in services/permission checks.

# 12. DIY Recipe — build your own custom user model
# Decide your identifier field (email, in your case) and inherit from AbstractUser (or AbstractBaseUser for even more control) plus any shared base class (BaseModel) your project uses.
# Remove any inherited fields you don't want, by setting them to None.
# Define your actual fields, choosing the right field type per kind of data, and blank/null per whether it's text (blank alone) vs. non-text (both).
# Set USERNAME_FIELD to your identifier field's name, and REQUIRED_FIELDS to whatever else createsuperuser should prompt for.
# Attach your custom manager: objects = YourManager().
# Add a nested Meta class for ordering, display names, and indexes on fields you know will be frequently filtered/queried.
# Add @property for any value that's purely computed from the model's own fields, with no database queries or side effects.
# Add __str__ so the model displays sensibly anywhere Django needs to show it as text.
# 13. General pattern recognition
# Multiple inheritance for "mix in framework behavior + project conventions" — you'll see this shape (class X(ProjectBase, FrameworkBase)) recur across every model in your project, not just User.
# String references for cross-app relationships ("company.Company") — the same circular-import-avoidance pattern as TYPE_CHECKING/forward references from the manager file, just Django's own built-in mechanism for ForeignKey specifically.
# @property for computed, dependency-free values — same shape you'll find on nearly every non-trivial Django model.
# 14. Real project usage

# This model sits at the absolute center of your RBAC system: require_owner() and require_permission() almost certainly check attributes on request.user (an instance of this exact class) — likely user.company, user.is_founder, and permissions inherited from AbstractUser/PermissionsMixin. Your GraphQL schema's me query, your OTP-based login flow, your admin's UserAdmin(BaseModelAdmin) — all of it operates on instances of this class.

# 15. Common beginner mistakes
# ❌ Forgetting to set USERNAME_FIELD when customizing the identifier field — login breaks in confusing ways.
# ❌ Leaving username = None out when removing username-based login — Django will still expect a username column to exist, causing migration/runtime errors.
# ❌ Importing the same name twice without realizing the second import silently shadows the first (exactly what's happening with UserManager here) — leads to confusion later about which class is actually in use.
# ❌ Using blank=True without null=True on a ForeignKey/DateTimeField/ImageField — forms will allow it empty, but the database will reject saving NULL, causing a runtime IntegrityError.
# ❌ Turning a genuinely expensive computation into a @property — since it looks like "just an attribute access," it's easy to accidentally call it in a loop (e.g., inside a queryset iteration) without realizing real work (or worse, a database query) happens every single time it's accessed.
# 16. Think like the original developer
# "I need a user model — Django gives me AbstractUser as a solid starting template, so I extend it rather than starting from zero."
# "My project also has shared conventions every model follows (id, timestamps) — I need those too, so I inherit from both."
# "My login identifier is email, not username — strip out username, add email as unique, and tell Django's auth system via USERNAME_FIELD."
# "What real-world facts does my project need to track about a user beyond the basics? Company membership, verification status, security lockout state, founder protection, avatar — model each as its own field, choosing types that match the real data shape."
# "Some of what I need isn't raw data — it's a simple computation from that data (full name, display name, lockout status). Those don't need their own database column; a @property keeps them always in sync."
# "I need my custom manager attached so user creation goes through the safe, centralized logic I already built."
# "Certain configuration (ordering, display names, performance indexes) isn't a field on the model — it's metadata about the model — so it belongs in Meta, not as a top-level attribute."

# That reasoning — "extend the framework's template, layer in project conventions, model real facts as fields and derived facts as properties, wire up the custom manager, and configure the rest via Meta" — is this file.
    
    
