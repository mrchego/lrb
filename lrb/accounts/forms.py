from allauth.account.forms import SignupForm
from allauth.socialaccount.forms import SignupForm as SocialSignupForm
from django.contrib.auth import forms as admin_forms
from django.forms import EmailField
from django.utils.translation import gettext_lazy as _
from lrb.accounts.models import User

class UserAdminChangeForm(admin_forms.UserChangeForm):
    class Meta(admin_forms.UserChangeForm.Meta):
        model = User
        field_classes = {"email": EmailField}
        
        
class UserAdminCreationForm(admin_forms.AdminUserCreationForm):
    class Meta(admin_forms.UserCreationForm.Meta):
        model = User
        fields = ("email",)
        field_classes = {"email": EmailField}
        error_message = {
            "email": {"unique": _("This email has already been taken.")},
        }
        
        
class UserSignupForm(SignupForm):
    pass

class UserSocialSignupForm(SocialSignupForm):
    pass


# forms.py — Admin & signup forms for the User model

# This file is shorter than the last one, but it introduces genuinely new concepts: third-party package integration (allauth), Meta classes that inherit from other Meta classes, and empty classes that exist purely for their position in an inheritance chain. Let's go through it carefully.

# 1. Purpose — What problem does this solve?

# Two separate systems in your project need forms built around your custom User model:

# Django's admin site — when a staff member views/edits a user in /admin/, or creates a brand-new user there, Django needs a form describing which fields to show and how to validate them. Django's built-in admin forms (UserChangeForm, UserCreationForm) assume the default User model shape (with username) — since your User uses email instead, those default forms need to be adapted.
# django-allauth — a widely-used third-party package (not written by you or Django itself) that handles the user-facing signup/login flow (the "create an account" page a real visitor fills out, as opposed to the admin backend). It also needs to know about your custom User model's shape.

# This file exists to bridge your custom User model into both of those systems, each of which ships its own generic default forms that need light customization to work with email-based, non-username accounts.

# Why not just use Django's/allauth's default forms unmodified? Because both were originally written assuming a username field exists. Your User model deliberately removed username (username = None, from the last file) — so the default forms would try to render/validate a field that no longer exists on your model, and would crash or behave incorrectly.

# When is this used? UserAdminChangeForm/UserAdminCreationForm — every time a staff member views, edits, or creates a user through Django's /admin/ site. UserSignupForm/UserSocialSignupForm — every time a real visitor signs up through your site's actual signup page (via allauth), either with an email/password form or by connecting a social account (Google, GitHub, etc.).

# What breaks without this file? Django's admin site and allauth's signup views would either error out immediately (referencing a username field that no longer exists) or silently behave in ways inconsistent with your actual User model's shape.

# 2. Imports — explained like you've never programmed
# python
# from allauth.account.forms import SignupForm
# from allauth.socialaccount.forms import SignupForm as SocialSignupForm
# from django.contrib.auth import forms as admin_forms
# from django.forms import EmailField
# from django.utils.translation import gettext_lazy as _
# from lrb.accounts.models import User

# allauth — this is the first import you've seen so far that's not part of Django itself. It's a separate, third-party Python package (installed via pip install django-allauth), written by an outside open-source team, that plugs into Django to add full account-management features (signup, login, email verification, social login) that Django's own django.contrib.auth doesn't fully provide out of the box. It's a real illustration of your earlier question — "is this built into Python? Did someone else write it?" — yes, someone else entirely wrote and maintains this, and your project has chosen to depend on it rather than build the same features from scratch.

# allauth.account.forms → SignupForm — allauth's own base class for the standard (email/password) signup form.

# allauth.socialaccount.forms → SignupForm as SocialSignupForm — a second, different class, also named SignupForm, but this one lives in allauth's socialaccount module — the part of allauth handling signup via a third-party login provider (e.g., "Sign up with Google"). Because this file already imported something called SignupForm on the line above, this one is renamed on import to SocialSignupForm to avoid a naming collision — exactly the same reasoning as UserManager as DjangoUserManager from two files ago.

# django.contrib.auth → forms as admin_forms — this time, instead of picking out one specific class, the entire module is imported and renamed to admin_forms. This module contains Django's own built-in admin-related form classes: UserChangeForm, UserCreationForm, AdminUserCreationForm. Importing the whole module (rather than each class individually) lets the rest of the file refer to them as admin_forms.UserChangeForm, admin_forms.AdminUserCreationForm, etc. — clearly signaling "these come from Django's admin forms module," which is useful here since this file is about to define its own differently-named classes that build on top of them.

# django.forms → EmailField — Django's plain form field class for an email input (distinct from models.EmailField, which you saw last file — that one defines a database column; this one defines a form input widget/validator, used when rendering an HTML <input> and validating submitted text).

# gettext_lazy as _ — the now-familiar translation helper.

# lrb.accounts.models → User — your actual custom User model from the previous file, imported directly and normally this time (no TYPE_CHECKING trick needed here, since forms.py isn't something models.py needs to import back — there's no circular dependency in this direction).

# 3. First class — UserAdminChangeForm
# python
# class UserAdminChangeForm(admin_forms.UserChangeForm):
#     class Meta(admin_forms.UserChangeForm.Meta):
#         model = User
#         field_classes = {"email": EmailField}

# Outer class signature:

# class UserAdminChangeForm(admin_forms.UserChangeForm): — inheritance again, same pattern as always: this form is a specialized version of Django's own UserChangeForm (the form Django's admin uses to edit an existing user).
# Why extend it instead of writing a form from scratch? Django's UserChangeForm already handles a lot of non-obvious behavior — like showing the user's hashed password as a read-only link ("change password" link, rather than a raw editable text field) and wiring up various admin-specific widgets. Rebuilding all of that yourself would be wasted, error-prone effort; overriding just the small parts that differ (which model, which field types) is far safer.

# The nested Meta class — and something genuinely new here:

# python
# class Meta(admin_forms.UserChangeForm.Meta):

# You've now seen class Meta: several times (in BaseModelAdmin... actually no, first properly in the User model file) as a plain, standalone nested class. This time, Meta itself has a parent in parentheses — admin_forms.UserChangeForm.Meta. This means: "my Meta configuration isn't starting from scratch either — it inherits whatever configuration Django's own UserChangeForm.Meta already had, and I'm only overriding specific pieces."

# Why go to the trouble of inheriting the inner Meta too, instead of just writing a fresh Meta from zero? Django's original UserChangeForm.Meta likely already sets useful things — like which widgets to use for certain fields, or the fields = "__all__" behavior showing every model field. If you wrote a brand new Meta with no inheritance, you'd lose all of that and have to manually reconstruct it. Inheriting the Meta too means: "keep everything Django already figured out; I'm just pointing it at my model and fixing the email field type."

# Body:

# model = User — tells this form: "the model you're building an edit form for is my custom User, not Django's default User." This is the single most important override — without it, the form would try to work against Django's built-in User model, which your project isn't even using.
# field_classes = {"email": EmailField} — a dictionary mapping one specific field name ("email") to a specific form field class (EmailField) to use for it. Django's admin form-generation machinery normally guesses an appropriate form field type based on the model field's type — but this line explicitly pins the email field to use Django's proper EmailField (which validates the text actually looks like a real email address), rather than leaving it to a generic guess.

# Whole class, plain English: "Build an admin edit-form for my custom User model, keeping all of Django's original UserChangeForm behavior, except explicitly making sure the email field is validated as a real email address."

# 4. Second class — UserAdminCreationForm
# python
# class UserAdminCreationForm(admin_forms.AdminUserCreationForm):
#     class Meta(admin_forms.UserCreationForm.Meta):
#         model = User
#         fields = ("email",)
#         field_classes = {"email": EmailField}
#         error_message = {
#             "email": {"unique": _("This email has already been taken.")},
#         }

# Same overall shape as the previous class, but for creating a new user through the admin (rather than editing an existing one), with a couple of new details:

# fields = ("email",)

# A tuple (parentheses, note the trailing comma — ("email",) is a one-item tuple; without that comma, ("email") would just be the string "email" in extra parentheses, not a tuple at all! This comma is easy to forget and a classic subtle Python trap.)
# Whole line: "The only field this creation form asks for directly is email" (password fields are handled separately/automatically by the parent AdminUserCreationForm, following Django's usual admin user-creation flow: create with email, set password in a follow-up step).

# error_message = {"email": {"unique": _("This email has already been taken.")}}

# A nested dictionary: the outer dictionary's key is "email" (which field this error applies to), and its value is another dictionary, whose key "unique" corresponds to a specific kind of validation failure (violating the unique=True constraint you saw on the email field in the User model), mapped to a custom, human-friendly, translatable message.
# Why override this message at all? Django's default uniqueness error message is generic ("User with this Email Address already exists.") — this line replaces it with clearer, more natural wording specific to this form.

# Notice the subtle difference in Meta inheritance between the two classes:

# UserAdminChangeForm's Meta inherits from admin_forms.UserChangeForm.Meta
# UserAdminCreationForm's Meta inherits from admin_forms.UserCreationForm.Meta — but the outer class itself inherits from admin_forms.AdminUserCreationForm (not UserCreationForm)!

# This is worth flagging directly: AdminUserCreationForm and UserCreationForm are two different classes in Django (the "Admin" version is a slight admin-specific variant Django introduced in more recent versions). Inheriting the outer class from one (AdminUserCreationForm) while inheriting the inner Meta from a different one (UserCreationForm.Meta) is unusual — normally you'd expect both to point at the same parent for consistency. This isn't necessarily broken (their Meta classes might be identical or compatible), but it's the kind of mismatch worth double-checking against Django's actual current source for whichever Django version you're running, since Django's own class naming/hierarchy here has shifted across versions.

# 5. UserSignupForm and UserSocialSignupForm — the empty classes
# python
# class UserSignupForm(SignupForm):
#     pass

# class UserSocialSignupForm(SocialSignupForm):
#     pass

# These are the simplest possible classes you've seen in this whole series: inheritance with an entirely empty body.

# What does an empty pass body actually mean here? It means: "This class inherits 100% of its parent's behavior, completely unchanged — I'm not overriding anything." So why even write the class at all, if nothing changes? Because of pass needing to exist syntactically — remember from your validator file, Python doesn't allow a truly empty class body; pass is the explicit "intentionally nothing here" placeholder.

# But if literally nothing is different, why not just use SignupForm and SocialSignupForm directly everywhere, without wrapping them in these two empty subclasses?

# This is one of the most important beginner questions in this entire file, and the answer is a real, common Django/allauth pattern: creating an intentional "hook point" for the future.

# Right now, your project might not need to customize signup at all — the base SignupForm behavior is fine as-is.
# But allauth's settings (in your settings.py) typically reference signup forms by dotted string path — e.g. ACCOUNT_FORMS = {"signup": "lrb.accounts.forms.UserSignupForm"}. If your settings already point at your project's own form class (UserSignupForm), then later, when you inevitably need to add a custom field to signup (say, requiring users to check "I agree to terms" or enter their company name), you only need to add that logic inside this one class — you never have to go back and change your settings file, because it was already pointing at your own class from day one.
# If you'd instead pointed your settings directly at allauth's own SignupForm, adding any custom signup behavior later would require going back and changing the settings reference, plus creating the new class then — more moving parts to coordinate, at the exact moment you're trying to ship a change.

# Whole classes, plain English: "Reserve a project-owned name for the signup form (and social signup form), currently behaving identically to allauth's defaults, so that customizing signup later is a one-file change."

# 6. Beginner questions, answered proactively

# Why are there two completely separate SignupForm classes (allauth.account.forms.SignupForm and allauth.socialaccount.forms.SignupForm) instead of one shared one? Because the information needed differs: signing up with email+password needs to collect a password; signing up via "Continue with Google" already gets identity info from Google and typically doesn't need a password field at all (Google handles authentication). allauth splits these into two purpose-built forms.

# Why field_classes = {...} as a dictionary instead of, say, a list of field names? Because it needs to map which field to what type of form field it should use — that's inherently a pairing, which is exactly what a dictionary (key → value) represents. A list alone couldn't express "email specifically uses EmailField."

# Why does Meta(admin_forms.UserChangeForm.Meta) use dotted access three levels deep — module, then class, then nested class? Because that's literally the containment hierarchy: admin_forms is the module; UserChangeForm is a class living inside that module; .Meta is a class living inside that class. Each dot walks one level deeper into that nesting, exactly like self.model.deleted_at walked from object → model → field in your admin file.

# Is pass here doing anything different from pass in ready(self): pass from your very first file? No — same meaning both times: "this block is syntactically required to have something, and I'm deliberately choosing 'nothing' for now."

# 7. Design discussion

# Why override field_classes for email specifically, if models.EmailField on the model already validates it's a proper email? Because model-level validation and form-level validation are separate layers that don't automatically imply each other. Django's admin auto-generates form fields by inspecting the model field's type — but explicitly pinning field_classes here removes any ambiguity/guessing, guaranteeing the form itself (client-facing input handling, before it ever reaches the model) enforces proper email formatting too, rather than relying on inference.

# Trade-off of the empty "hook point" pattern (UserSignupForm(SignupForm): pass): It costs a few extra lines of code for something that currently does nothing — a beginner might reasonably ask "why not add this only when I actually need custom signup logic?" The trade-off is about where the pain happens: writing the empty class now costs almost nothing; not writing it means that later, adding custom signup fields requires touching both your forms file and your settings file at the same time, right when you're trying to ship a feature. Front-loading the empty class trades a tiny bit of now-cost for a smoother later-change.

# 8. DIY Recipe — adapting third-party/framework forms to a custom model
# Identify which built-in form (Django admin's, or a third-party package's) assumes a shape your model no longer has (e.g., assumes username exists).
# Create a subclass of that form, and — separately — a subclass of its inner Meta (inheriting from the parent's Meta too, to preserve unrelated existing configuration).
# In your new Meta, override model to point at your actual model.
# Override fields/field_classes/error_message only for the specific fields that need explicit handling — leave everything else inherited.
# For forms from packages that support pluggable form classes via settings (like allauth), create an empty subclass now, even with no custom behavior yet, and point your settings at that subclass from the start — this reserves a clean hook for future customization.
# 9. General pattern recognition
# The "adapter/customization subclass" pattern: subclass a framework's default class, override only the specific config that differs (here: model, a couple of field_classes, an error message), and lean on inheritance for everything else. You've now seen this shape in BaseModelAdmin(admin.ModelAdmin), UserManager(DjangoUserManager), and now these form classes — it's the dominant pattern across this entire codebase.
# Nested config classes that themselves inherit (class Meta(ParentForm.Meta)) — a slightly more advanced variant of the plain Meta pattern, specifically for preserving a parent's configuration while adding your own.
# The "empty hook class" pattern (class X(Y): pass) — reserving a project-owned name pointing at framework defaults, anticipating future customization without requiring it now.
# 10. Real project usage
# UserAdminChangeForm/UserAdminCreationForm get wired into your UserAdmin(BaseModelAdmin) class (the admin class from a couple of files ago), via form = UserAdminChangeForm and add_form = UserAdminCreationForm attributes, so Django's admin uses these instead of its defaults when managing users.
# UserSignupForm/UserSocialSignupForm get referenced in settings.py under allauth's ACCOUNT_FORMS/SOCIALACCOUNT_FORMS settings, so your project's actual public signup pages use them.
# 11. Common beginner mistakes
# ❌ Forgetting the trailing comma in a one-item tuple — fields = ("email") is just the string "email", not a tuple, and would silently break/misbehave rather than throwing an obvious error.
# ❌ Forgetting to also inherit the nested Meta class from the parent's Meta (class Meta: instead of class Meta(Parent.Meta):) — silently loses whatever configuration the parent had already set up.
# ❌ Mixing up which parent class's Meta to inherit from when Django itself has multiple similarly-named classes (UserCreationForm vs AdminUserCreationForm) across versions — worth double-checking against the installed Django version's actual source.
# ❌ Creating pass-only subclasses without actually wiring them into settings — the whole point of the "hook" pattern is defeated if ACCOUNT_FORMS still points at allauth's original classes instead of yours.
# ❌ Importing two classes with the same name from different modules without renaming one via as — causes a silent shadowing bug, same risk you already saw with the double UserManager import in the User model file.
# 12. Think like the original developer
# "Django's admin and allauth both ship generic forms assuming a username-based User — but my model doesn't have that. I need to adapt, not replace, their forms."
# "Subclassing is safer than rewriting — I keep all their existing, battle-tested behavior, and only touch what actually differs: which model, which field types, which error text."
# "The nested Meta needs the same treatment as the outer class — inherit it too, don't start it from scratch, or I'll lose configuration I don't even know exists yet."
# "For allauth specifically, since it looks up my form classes by name/path from settings, I should point those settings at my own class names from day one — even if they do nothing special yet — so I never have to touch settings again when I inevitably need to customize signup."
# "Nothing here needs new logic yet — so wherever nothing needs to change, an empty pass subclass is the correct, minimal, forward-compatible choice."

# That reasoning — "adapt via subclassing rather than rewriting, preserve inherited config by inheriting Meta too, and reserve empty hook classes wherever a future customization point might be needed" — is this file.