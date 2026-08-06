from django.db import models
from .mixins import TimeStampedMixin, UUIDMixin

class BaseModel(UUIDMixin, TimeStampedMixin, models.Model):
    class Meta:
        abstract = True
        
        
# core/models.py — BaseModel
# 1. Purpose (Why this exists)

# What problem is this solving? We just built three separate mixins — UUIDMixin, TimeStampedMixin, SoftDeleteMixin — each contributing a small, focused piece of behavior. But most models in your project probably want the combination of UUID + timestamps together, every single time. Without this file, every single model in your project would have to write:

# python
# class Company(UUIDMixin, TimeStampedMixin, models.Model):
#     ...

# repeating that same two-mixin combination on every model. BaseModel exists to bundle "the two things almost every model wants" into one single thing to inherit from, so you only have to type UUIDMixin, TimeStampedMixin together once — right here.

# Why couldn't we just write the logic directly on each model? You could inherit both mixins separately on every model — but then if you ever decided "actually, every model should also get a fourth shared behavior," you'd have to go edit every single model file, instead of editing this one BaseModel.

# When is this used in a real project? Any time you create a new model that needs a UUID primary key and timestamps (which is most models), you'd inherit from BaseModel instead of listing out UUIDMixin, TimeStampedMixin by hand.

# What happens if this doesn't exist? Nothing breaks technically — you could still use the two mixins separately everywhere — but you'd lose the convenience of "one name to inherit from," and you'd have a slightly higher chance of someone forgetting one of the two mixins on a new model.

# 2. Imports — explained like you've never programmed
# python
# from django.db import models

# Same as the mixins file — Django's toolbox for defining models and fields. Here it's used just to give this class access to models.Model (needed because of how Python's multiple inheritance works with Meta/abstract, explained below).

# python
# from .mixins import TimeStampedMixin, UUIDMixin

# This is new — notice the dot before mixins: .mixins, not just mixins. This is a relative import — it means "look for a file called mixins.py in the same folder as this current file," rather than searching your whole project or Python's installed packages. Since BaseModel lives in the same app/folder as the mixins file we just built, this is the natural way to reference it. If you moved mixins.py to a different folder, this import would need to change to reflect the new relative location.

# 3 & 4. The class
# python
# class BaseModel(UUIDMixin, TimeStampedMixin, models.Model):

# Why a class here? Same mixin idea as before — this isn't meant to be a real, standalone database table; it's a combination point, gluing two mixins together into one reusable base.

# Why does it inherit from three things at once — UUIDMixin, TimeStampedMixin, and models.Model? This is genuinely worth slowing down on, since it looks redundant at first (UUIDMixin and TimeStampedMixin already each inherit from models.Model themselves, as you saw in the last file). This is multiple inheritance — Python lets a class inherit from more than one parent class at once, listed comma-separated inside the parentheses. Python combines the fields/behavior from all the listed parents into this one new class. Including models.Model explicitly here, even though the other two mixins already inherit from it, is a defensive, common Django convention — it makes the intention completely explicit ("this is definitely a Django model base"), and avoids relying on Python correctly figuring out the shared ancestor through the mixins alone in every possible situation. It's not strictly required here, but it's a safe habit that avoids subtle inheritance-order issues in more complex mixin combinations.

# What does "combine" actually mean here in practice? Any real model that inherits from BaseModel ends up with: id (from UUIDMixin), created_at and updated_at (from TimeStampedMixin), plus everything models.Model itself provides (like .save(), .delete(), and all of Django's ORM query machinery) — all without BaseModel itself writing a single new field.

# python
#     class Meta:
#         abstract = True

# Exact same reasoning as every mixin — BaseModel itself should never become a real database table; it only exists to be inherited from.

# 6. Beginner questions, answered

# Why isn't SoftDeleteMixin included here too, if it's also a shared mixin? This is the actual design question worth sitting with — covered fully below.

# Does the order of UUIDMixin, TimeStampedMixin, models.Model matter? In Python, when multiple parent classes define something with the same name, the order listed determines which one "wins" if there's a conflict (Python looks left to right). Here, there's no actual conflict — UUIDMixin defines id, TimeStampedMixin defines created_at/updated_at, and neither overlaps with the other's fields — so in this specific case, the order doesn't change behavior. But it's a good habit to know why order can matter in Python multiple inheritance generally, for cases where it does.

# 7. Design Discussion

# Why does BaseModel combine UUIDMixin + TimeStampedMixin, but deliberately leave SoftDeleteMixin out?

# This is a real, sensible design decision, not an oversight: UUID and timestamps are things every single model in the project almost certainly wants — there's no real downside to any model having a created_at. But soft-delete is not universal — some models (like a VerificationCode, which is meant to just expire and get cleaned up, not be "undo-deleted") genuinely shouldn't have is_deleted/deleted_at fields at all; they're meaningless there.

# If SoftDeleteMixin had been folded into BaseModel, every model would be forced to carry those extra fields whether they make sense or not — adding unnecessary columns to tables that will never use them. By keeping it separate, each individual model can opt in:

# python
# class Company(BaseModel, SoftDeleteMixin):
#     name = models.CharField(max_length=255)
#     class Meta:
#         pass

# while a model like VerificationCode can just use BaseModel alone, skipping soft-delete entirely.

# General principle to bank: when combining reusable pieces into a larger "starter pack," only bundle together what's genuinely universal. Anything optional/situational should stay separate, so each user of your code can opt in deliberately rather than being forced to carry things they don't need.

# 8. DIY Recipe — How to Build Your Own Combined Base Class
# Look at your existing mixins and ask: which ones does almost every model in this project need? Only those belong in a shared BaseModel.
# Create a new class inheriting from those universal mixins, plus models.Model explicitly (the defensive convention above).
# Always add class Meta: abstract = True.
# Leave situational mixins (like soft-delete) out — let individual models opt into those separately, alongside BaseModel.
# Use this BaseModel as the default starting point for every new model you create, adding only situational mixins and the model's own specific fields on top.
# 9. General Pattern Recognition
# Several small, focused mixins exist
#        ↓
# Identify which ones are truly universal (needed by ~every model)
#        ↓
# Combine just those into one convenience base class
#        ↓
# Leave situational/optional mixins separate, to be added individually where needed

# This "universal base + optional add-ons" shape is extremely common — you'll see the same idea in almost any framework with reusable building blocks (e.g., a base API response class most endpoints use, plus optional mixins like pagination or caching that only some endpoints need).

# 10. Real project usage

# In your RBAC project, this is very likely what most of your real models — User, Company, Role, Product — actually inherit from directly, something like:

# python
# class Role(BaseModel):
#     name = models.CharField(max_length=100)
#     class Meta:
#         pass

# getting a UUID primary key and timestamps automatically, with each model only adding the fields specific to its own purpose.

# 11. Common beginner mistakes
# ❌ Bundling every mixin into one giant BaseModel, forcing all models to carry fields they'll never use (like soft-delete fields on a model that should never be "restorable").
# ❌ Forgetting abstract = True here too — same consequence as before, an unwanted real database table.
# ❌ Assuming BaseModel(UUIDMixin, TimeStampedMixin) (without explicitly including models.Model) wouldn't work — it actually would, since both mixins already inherit from models.Model themselves — but omitting it loses the explicit, defensive clarity this convention provides.
# 12. Think like the original developer
# "I've built a few small, focused mixins — but I noticed I'm about to type UUIDMixin, TimeStampedMixin together on almost every model I create."
# "That repetition itself is worth eliminating — I'll make one more class that just combines the ones I always want together."
# "But I shouldn't include every mixin — only the ones that are genuinely universal. Soft-delete isn't something every model needs, so I'll leave that one out, letting individual models opt in only when it actually makes sense for them."
# "This new combined class is still just a convenience — it shouldn't become a real table either, so it needs abstract = True just like its ingredients."