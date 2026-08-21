from  __future__ import annotations
from typing import TYPE_CHECKING
from django.contrib.auth.models import UserManager as DjangoUserManager

if TYPE_CHECKING:
    from .models import User
    
class UserManager(DjangoUserManager[User]):
    def _create_user(self, email: str, password: str | None, **extra_fields):
        if not email:
            raise ValueError("The given email must be set")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user
    
    def create_user(self, email:str, password:str | None = None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)
    
    def create_superuser(self, email: str, password: str | None =  None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self._create_user(email, password, **extra_fields)
    
    
#     1. Purpose — What problem does this solve?

# Django's built-in User model normally uses username as the login field. Your RBAC project uses email-based login instead (no username field at all). Django's default manager (UserManager) doesn't know how to create users that way — it expects a username.

# This file overrides Django's manager to teach it: "when creating a user, use email as the unique identifier, not username." It also centralizes the logic for the two ways a user account can be created in your system:

# A normal user (create_user) — via signup, admin panel, etc.
# A superuser (create_superuser) — via python manage.py createsuperuser, Django's own admin bootstrapping command.

# Why not just write User.objects.create(...) directly wherever you need a new user? Because creating a user correctly involves several non-obvious steps that must always happen together: normalizing the email (so Test@Example.com and test@example.com aren't treated as different accounts), hashing the password (never storing it in plain text), and saving to the right database. If you scattered this logic across every signup form, GraphQL mutation, and admin script, it would be trivial to someday forget set_password() and accidentally save a plain-text password. Centralizing it in one manager means there's exactly one correct way to create a user, and everything funnels through it.

# When is this used? Every single time a User object is created anywhere in the project — signup, createsuperuser, seed scripts, tests.

# What breaks without it? Django's default manager assumes a username field exists. Since your custom User model uses email as the login identifier instead (a common pattern), Django's default manager would crash or behave incorrectly — it has no idea your model doesn't have a username.

# 2. Imports — explained like you've never programmed
# python
# from typing import TYPE_CHECKING
# from django.contrib.auth.models import UserManager as DjangoUserManager

# typing — a built-in Python module (not Django-specific) whose entire purpose is providing tools for type hints — the : str / -> None style annotations you saw in the last file, but for more advanced cases.

# TYPE_CHECKING — a special constant. It's False while your program is actually running, but tools like mypy (static type checkers) pretend it's True when analyzing your code without running it. This lets you import things only for type-hinting purposes, without those imports actually happening at runtime. You'll see exactly why this matters in a moment.

# django.contrib.auth.models — the part of Django responsible for authentication-related models: User, permissions, groups, and — relevant here — UserManager, Django's default logic for creating users.

# UserManager as DjangoUserManager — importing Django's original UserManager class, but renaming it on import to DjangoUserManager.

# Why rename it? Because this file itself is about to define its own class also called UserManager. If you imported Django's version under its original name, you'd have two different things both called UserManager in the same file — a naming collision. Renaming the import avoids that clash while still making clear where it came from ("the Django one").

# python
# if TYPE_CHECKING:
#     from .models import User

# if TYPE_CHECKING: — reads exactly like a normal if, but since TYPE_CHECKING is False at runtime, this import never actually executes when your program runs. It only "happens" from the perspective of a type-checking tool reading your code.

# from .models import User — the . means "from the current package" (i.e., the models.py file sitting right next to this one, in the same app folder). We're importing the User model class.

# Why guard this import behind TYPE_CHECKING instead of just importing User normally at the top? This is solving a classic Django problem called a circular import. Managers are typically attached to models (you'll see objects = UserManager() inside the User model class itself). If managers.py imported models.py directly at the top level, and models.py also needs to import the manager class from managers.py to attach it — each file would be trying to load the other before either one has finished loading, causing a crash. Hiding the import behind TYPE_CHECKING means: "only pretend to import User when a type-checker is analyzing the code (which doesn't actually run your program, so no circular loading problem occurs) — but never actually import it while the program is really running."

# Could you write your own package like django? As with earlier files — yes, structurally there's nothing different between "code someone else published" and "code you write," it's the same language.

# 3. Class Signature — every symbol explained
# python
# class UserManager(DjangoUserManager["User"]):

# class UserManager — defining a new class named UserManager. This name matching Django's own naming convention is deliberate and expected — Django projects commonly override UserManager under the exact same name their custom manager is meant to replace.

# (DjangoUserManager["User"]) — inheritance, same concept as your earlier files (CoreConfig(AppConfig), BaseModelAdmin(admin.ModelAdmin)). This class is a specialized version of Django's original manager.

# What's the ["User"] part — square brackets on a class we're inheriting from?
# This is a generic type parameter. DjangoUserManager is written (in Django's own source) as a generic class — meaning it can be "specialized" for different model types. Writing DjangoUserManager["User"] tells type-checking tools: "this specific manager is a UserManager that manages the User model specifically" (as opposed to some other model).

# Does this affect runtime behavior? No — exactly like the : str type hints from your last file, this is purely informational for tools/humans. At runtime, Python doesn't actually restrict or check what model type the manager works with because of this bracket syntax.

# Why is "User" in quotes?
# Because of that same circular-import problem — at the moment this line runs, User hasn't actually been imported (remember, the real import only happens inside if TYPE_CHECKING:, which is skipped at runtime!). Writing it as a plain string "User" (called a forward reference) means: "I'm referring to something named User that will exist, without needing it to actually be loaded and available right now." Type-checking tools understand this convention and resolve the string reference back to the real User class using the TYPE_CHECKING import above; Python itself, at runtime, just treats it as an inert string.

# 4. Classes — why this design

# Why override the whole class instead of just writing three standalone functions?
# Because Django's model system expects User.objects to be a manager instance — an object with .create_user(), .create_superuser(), and (inherited) many other query methods like .filter(), .get(), etc. A manager needs to be a class so it can bundle all of that querying/creation behavior together into one object that gets attached to the model (objects = UserManager()).

# What is self referring to here?
# The specific manager instance attached to the User model — typically accessed as User.objects. So inside these methods, self.model refers to the User class itself, and self.normalize_email(...) calls a helper method inherited from Django's base manager.

# 5. _create_user — line by line (the shared internal logic)
# python
# def _create_user(self, email: str, password: str | None, **extra_fields):
#     if not email:
#         raise ValueError("The given email must be set")
#     email = self.normalize_email(email)
#     user = self.model(email=email, **extra_fields)
#     user.set_password(password)
#     user.save(using=self._db)
#     return user

# Signature first:

# _create_user — the leading underscore is a Python convention (not a hard rule Python enforces) meaning "this is a private/internal method — not meant to be called from outside this class." It exists so create_user and create_superuser can share one implementation, without exposing that shared internal logic as part of the manager's public interface.
# email: str — a required parameter, hinted as a string.
# password: str | None — a required parameter, hinted as "either a string, or None." The | here means "or" between types (a modern Python type-hint syntax). This communicates: "a user can be created with no password set yet" (unusual, but valid — e.g., an account created by an admin, awaiting the user to set their own password later via an invite link).
# **extra_fields — double-star in a function signature means "collect any number of extra keyword arguments the caller provides, that aren't already named above, into a dictionary called extra_fields." This is exactly the **kwargs pattern from your very first document's *args/**kwargs explanation — except named descriptively (extra_fields) instead of the generic kwargs. It lets callers pass arbitrary additional model fields (e.g. first_name="Jane", is_active=True) without this function needing to know about every possible field your User model might have.

# Line 1-2:

# python
# if not email:
#     raise ValueError("The given email must be set")
# not email — not flips a truthy/falsy value. An empty string "" (or None) is considered "falsy" in Python, so not email is True exactly when email is empty/missing.
# Whole guard clause (same fail-fast pattern from your last file): "If no email was given, stop immediately and report the problem."
# Why ValueError here instead of ValidationError like your last file? This is a deliberate, meaningful distinction. ValidationError is for user-facing input validation — things a form/API caller might legitimately get wrong, that Django knows how to display nicely. ValueError is Python's own generic built-in exception for "a function received an inappropriate value" — used here because calling create_user() with no email is treated as a programmer error (a bug in code calling this manager incorrectly), not something an end-user would ever directly trigger through a form (forms would have their own separate validation before ever reaching this manager method).

# Line 3: email = self.normalize_email(email)

# Right side: self.normalize_email(email) — a method inherited from Django's base manager. It lowercases the domain portion of the email (the part after @) for consistency, since domains are case-insensitive by spec, while leaving the local part (before @) untouched, since that portion technically can be case-sensitive per email standards.
# Left side: overwrite the local email variable with this normalized version.
# Whole line: "Standardize the email's formatting before using it further."

# Line 4: user = self.model(email=email, **extra_fields)

# self.model — every Django manager automatically knows which model class it's attached to (this is set up by Django internally when you write objects = UserManager() inside the User model). So self.model here is the User class itself.
# self.model(email=email, **extra_fields) — calling the model class like a function actually constructs a new (unsaved) instance of it — this is standard Python: calling a class creates an object. email=email passes the normalized email as a keyword argument. **extra_fields — this time, double-star on the calling side means the opposite of before: "unpack this dictionary back out into individual keyword arguments." So if extra_fields was {"first_name": "Jane"}, this line effectively becomes self.model(email=email, first_name="Jane").
# Whole line: "Build a new (not-yet-saved) User object in memory, with this email and any other provided fields."

# Line 5: user.set_password(password)

# user.set_password(...) — a method every Django user model gets for free (inherited from AbstractBaseUser). It hashes the given password (using Django's configured hashing algorithm, e.g. PBKDF2/Argon2) and stores that hash on the object — critically, it does not store the plain-text password anywhere.
# Why not just do user.password = password? Because that would store the raw, plain-text password directly in the database — a severe security flaw. set_password() is the only correct way to set a password on a Django user.
# What if password is None? Django's set_password(None) sets the password to an unusable-but-valid-looking hash, effectively meaning "this account has no usable password" (it can't be logged into via password auth until a real password is set) — this is intentional, supporting the "admin creates account, user sets password later" flow mentioned earlier.

# Line 6: user.save(using=self._db)

# user.save(...) — writes this in-memory object to the actual database (an INSERT statement, since it's a new object).
# using=self._db — tells Django which specific database to save to. self._db is set internally by the manager depending on context (relevant in multi-database Django setups — e.g., if you have a read-replica configuration, or route certain writes to a specific database). For most single-database projects this is just "the default database," but including it is defensive best practice matching Django's own internal UserManager implementation, so this manager correctly respects multi-database routing if it's ever introduced.

# Line 7: return user

# Hands back the newly created, saved User object to whoever called _create_user.

# Whole method, plain English: "Make sure an email was provided, standardize its formatting, build a new user with that email plus any other given fields, securely hash and set the password, save it to the database, and return the finished user object."

# 6. create_user — line by line
# python
# def create_user(self, email: str, password: str | None = None, **extra_fields):
#     extra_fields.setdefault("is_staff", False)
#     extra_fields.setdefault("is_superuser", False)
#     return self._create_user(email, password, **extra_fields)

# Signature difference from _create_user: notice password: str | None = None — this time it has a default value, = None. So calling create_user("test@example.com") with no password argument at all is valid — it'll assume None. _create_user required password to always be explicitly passed; create_user (the public-facing method) is more forgiving.

# extra_fields.setdefault("is_staff", False)

# .setdefault(key, value) — a dictionary method meaning: "if key is not already present in this dictionary, add it with value. If it's already there, leave it untouched." This is different from just doing extra_fields["is_staff"] = False, which would overwrite any existing value.
# Whole line: "Unless the caller already explicitly specified is_staff, default it to False."

# Why does a regular user creation function need to set is_staff/is_superuser at all, even to False?
# Because it's explicit and defensive — rather than relying on whatever self.model(...) happens to default these fields to (which depends on how the model itself is defined), this method makes the intent unmistakable: "a normal user, by default, is not staff and not a superuser," directly at the point of creation. It also means if a caller does pass is_staff=True deliberately (an edge case, but possible), setdefault respects that instead of silently overriding it.

# Last line: return self._create_user(email, password, **extra_fields)

# Delegates the actual work to the shared internal method you just read, now that the staff/superuser defaults have been applied on top of whatever the caller provided.
# Notice: email and password are passed positionally here (no keyword=), while **extra_fields unpacks the rest as keywords — matching exactly how _create_user's signature expects them.
# 7. create_superuser — line by line
# python
# def create_superuser(self, email: str, password: str | None = None, **extra_fields):
#     extra_fields.setdefault("is_staff", True)
#     extra_fields.setdefault("is_superuser", True)
#     if extra_fields.get("is_staff") is not True:
#         raise ValueError("Superuser must have is_staff=True.")
#     if extra_fields.get("is_superuser") is not True:
#         raise ValueError("Superuser must have is_superuser=True.")
#     return self._create_user(email, password, **extra_fields)

# First two lines — same .setdefault() pattern as create_user, but flipped: default both is_staff and is_superuser to True this time, since a superuser is expected to have both.

# Then two guard clauses:

# python
# if extra_fields.get("is_staff") is not True:
#     raise ValueError("Superuser must have is_staff=True.")
# extra_fields.get("is_staff") — a dictionary method that safely retrieves the value for "is_staff", returning None if the key somehow isn't present (rather than crashing, which is what extra_fields["is_staff"] would risk doing if the key were missing).
# is not True — checks specifically whether the value is not exactly the boolean True (as opposed to just != True, which — for subtle Python reasons involving how 1/0 compare to booleans — is a slightly less strict check; is not True guarantees you're checking for the actual True object).
# Whole guard: "If, after applying defaults, is_staff still isn't exactly True — someone must have explicitly passed is_staff=False — stop and report the contradiction."

# Why check this after already calling setdefault(..., True) — doesn't setdefault guarantee it's True?
# This is the key insight: setdefault only sets the value if it's missing. If a caller deliberately calls create_superuser(email, password, is_staff=False), that explicit False is already present in extra_fields before setdefault runs — so setdefault does nothing (the key's already there), and is_staff stays False. These two guard clauses exist specifically to catch that contradiction: someone asking for a superuser while explicitly denying staff status, which makes no sense in Django's permission model (superusers are required to also be staff to access the admin site) — and refuse to silently create a broken/inconsistent account.

# Final line: same delegation to _create_user as before, now with validated, guaranteed-True staff/superuser flags.

# 8. Beginner questions, answered proactively

# Why does _create_user take password as required (no default), but create_user/create_superuser give it a default of None?
# _create_user is the shared internal engine — by the time anything calls it, the calling code (create_user/create_superuser) has already decided what password should be (even if that decision is "no password was given, so None"). Making it required in _create_user is a small safety net: it forces every caller of the internal method to be explicit about that decision, rather than relying on yet another layer of defaulting.

# Why **extra_fields instead of just listing every possible field explicitly, like first_name=None, last_name=None, ...?
# Because this manager shouldn't need to know or care about every field your User model might ever have. If you add a new field to User later (say, phone_number), this manager code doesn't need to change at all — **extra_fields automatically forwards it through. This is exactly the **kwargs reasoning from your first document: "you don't want to rewrite this every time the thing it wraps changes."

# Why is _create_user "private" (underscore) but called from two other methods in the same class — isn't that contradictory?
# No — the underscore convention means "don't call this from outside the class," not "don't call this at all." Other methods within the same class are expected to use it; that's the whole point of extracting shared logic into one internal helper.

# What does self.model(email=email, **extra_fields) actually construct, exactly?
# An instance of whatever model self.model refers to — in this case, your User model. It hasn't touched the database yet at this line; it exists only in memory until .save() is called two lines later.

# 9. Design discussion

# Why go through all this trouble instead of just calling User.objects.create(email=..., password=...) directly?
# Django's default .create() (inherited generically from any manager/queryset) does not hash passwords — it would store whatever you pass to password= completely as-is, in plain text. This whole custom manager exists specifically to make sure set_password() (the hashing step) can never be skipped, by ensuring the only sanctioned way to create a user goes through this manager's methods.

# Why separate create_user and create_superuser instead of one function with an is_superuser=True/False flag?
# Partly Django convention (Django's createsuperuser management command specifically expects a manager method named exactly create_superuser to exist), and partly safety: create_superuser's extra validation guard clauses (checking that both flags end up True) exist precisely because superuser creation is higher-stakes — mixing that validation into a single generic function would either weaken the check for normal users or add irrelevant checks to the common case.

# Trade-off of **extra_fields flexibility: It's convenient and future-proof, but it also means typos in field names (e.g. is_staff=True instead of is_staff=True) won't be caught by this manager at all — they'll just get silently passed through to self.model(...), and Django will raise its own (less obvious) error at that point, or worse, silently create an unexpected field if your model happens to allow arbitrary attributes. Explicit named parameters would catch such typos immediately with a clear TypeError, at the cost of needing to update this file every time the model gains a new field.

# 10. DIY Recipe — build your own custom user manager
# Identify your model's unique identifier field (here: email instead of Django's default username).
# Write one private _create_user(self, <identifier>, password, **extra_fields) method containing the actual shared creation steps: validate the identifier is present → normalize it if applicable → build the unsaved model instance → set_password() → save(using=self._db) → return it.
# Write a public create_user(...) method with sensible, permission-safe defaults (e.g. is_staff=False), that delegates to your private method.
# Write a public create_superuser(...) method with elevated defaults (e.g. is_staff=True, is_superuser=True), plus explicit guard clauses re-verifying those elevated flags actually stuck (catching any contradictory arguments the caller passed), before delegating to the same private method.
# If your manager needs to reference your model class for type hints, and that would create a circular import, guard the import behind if TYPE_CHECKING: and reference the class as a string ("User") wherever needed in the signature.

# This recipe generalizes to any Django project using a non-default identifier field for authentication.

# 11. General pattern recognition

# Two patterns stack together here:

# The shared-private-helper pattern (also seen conceptually in BaseModelAdmin's get_readonly_fields): multiple public entry points (create_user, create_superuser) funnel into one private implementation (_create_user), so the actual risky/important logic (password hashing, saving) exists in exactly one place.
# Defaults-then-verify guard pattern: setdefault(...) followed immediately by an explicit if ... is not True: raise ... check. This shows up anywhere code needs to apply a default while still catching a caller who explicitly contradicts that default — you'll see this same shape in permission-checking code, config-loading code, and anywhere "sensible defaults, but don't let anyone quietly override the sensible part into something dangerous" matters.
# 12. Real project usage

# This manager gets attached inside your User model, roughly:

# python
# class User(AbstractBaseUser, PermissionsMixin):
#     email = models.EmailField(unique=True)
#     ...
#     objects = UserManager()

# From that point on, User.objects.create_user(email="new@example.com", password="...") is what your signup service function calls, and python manage.py createsuperuser automatically calls create_superuser(...) behind the scenes to bootstrap your very first admin account.

# 13. Common beginner mistakes
# ❌ Setting user.password = raw_password directly instead of user.set_password(raw_password) — stores a plain-text password, a severe security bug.
# ❌ Forgetting save(using=self._db) and just calling .save() — usually works fine in single-database setups, but breaks multi-database routing if it's ever introduced.
# ❌ Using extra_fields["is_staff"] = False instead of .setdefault(...) — this would overwrite a value the caller explicitly passed in, rather than only filling in a missing one.
# ❌ Skipping the re-verification guard clauses in create_superuser (trusting setdefault alone) — allows a caller to silently create a "superuser" that's actually missing is_staff/is_superuser, breaking admin access unexpectedly.
# ❌ Importing User normally at the top of a managers file that the model itself needs to import from — causes a circular import crash; forgetting the TYPE_CHECKING guard is a very common beginner Django mistake.
# ❌ Confusing ValueError and ValidationError — using ValidationError here would be technically functional but semantically wrong, since Django's form/serializer error-display machinery wouldn't ever actually see it (this is a programmer-facing contract, not user input).
# 14. Think like the original developer
# "My login field is email, not username — Django's default manager assumes username, so I need my own."
# "Every path to creating a user — normal signup, superuser bootstrapping — shares the exact same critical steps: validate the identifier, normalize it, hash the password, save. I should write that once, privately, and have everything else call it."
# "Normal users and superusers differ only in their default permission flags — so I need two thin public wrappers around that one shared core, each supplying different defaults."
# "For superuser creation specifically, the stakes are higher — I shouldn't just assume my defaults stuck; I should double-check after applying them, in case the caller tried to sneak in a contradictory value."
# "I want this manager to survive future changes to the User model without needing edits — so I'll accept arbitrary extra fields via **extra_fields rather than hardcoding every field name."
# "If I need to type-hint against my own User model, but that would create an import loop with the model file that uses this manager — I need to hide that import from actually running, while still keeping it available for type-checking tools."

# That chain — "identify the real identifier field, centralize the dangerous steps once, layer thin permission-specific wrappers on top, verify rather than assume, stay forwards-compatible with **kwargs, and dodge the circular import with TYPE_CHECKING" — is this file.