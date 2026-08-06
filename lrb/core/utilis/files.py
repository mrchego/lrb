import os
import time
import uuid


def generic_upload_path(subfolder, filename, *, unique_name=None):
    _, ext = os.path.splitext(filename)
    ext = ext.lower()
    name = unique_name or str(uuid.uuid4())
    return os.path.join(subfolder, f"{name}{ext}")


def avatar_upload_path(instance, filename):
    if not hasattr(instance, "company_id"):
        raise AttributeError(
            f"avatar_upload_path expects a User-like instance with "
            f"'company_id', got {type(instance).__name__}."
        )
    subfolder = os.path.join("companies", str(instance.company_id), "avatars")
    unique_name = f"user_{instance.id}_{int(time.time())}"
    return generic_upload_path(subfolder, filename, unique_name=unique_name)


def company_logo_light_upload_path(instance, filename):
    subfolder = os.path.join("companies", str(instance.id), "logos")
    unique_name = f"light_{int(time.time())}"
    return generic_upload_path(subfolder, filename, unique_name=unique_name)


def company_logo_dark_upload_path(instance, filename):
    subfolder = os.path.join("companies", str(instance.id), "logos")
    unique_name = f"dark_{int(time.time())}"
    return generic_upload_path(subfolder, filename, unique_name=unique_name)

# 1. Purpose (why this exists)

# This is the same file from before, now with one extra improvement: it doesn't just avoid filename collisions between different users — it now also avoids cache problems when the same user re-uploads a new photo. Every time a file goes up, it lands in a predictable, organized folder (grouped by company), but with a fresh, never-before-seen filename, so old cached copies in browsers don't get shown by mistake.

# 2. The imports
# python
# import os

# Toolbox for building file paths and splitting filenames from extensions — same as before.

# python
# import time

# New addition. This is Python's built-in toolbox for anything involving the current date/time. We're using exactly one tool from it: time.time().

# python
# import uuid

# Same as before — used here only as a fallback, for generating a random unique value when no specific unique_name is given.

# 3. generic_upload_path — the shared engine
# python
# def generic_upload_path(subfolder, filename, *, unique_name=None):

# Three inputs:

# subfolder — which folder this file should live in.
# filename — the original filename the browser sent.
# *, unique_name=None — everything after the bare * must be passed by name (same rule as paginate_queryset's limit/offset — this exists here because filename and unique_name are both plain text, easy to accidentally swap). unique_name is optional — if the caller doesn't provide one, it defaults to None.
# python
#     _, ext = os.path.splitext(filename)

# Splits "photo.JPG" into two pieces — the name (thrown away into _, meaning "I don't need this") and the extension (kept as ext, e.g. .JPG).

# python
#     ext = ext.lower()

# Forces the extension to lowercase — .JPG becomes .jpg — so capitalization never causes inconsistent-looking filenames.

# python
#     name = unique_name or str(uuid.uuid4())

# This is the "pick one of two options" pattern you've now seen several times (code or ErrorCode.APPLICATION_ERROR, offset or 0):

# If unique_name was actually given something (like "user_5_1699999999"), use that.
# If unique_name is None (nothing given), fall back to generating a completely random UUID instead, converted to text with str(...).

# This is what makes generic_upload_path flexible — sometimes you want a specific, meaningful filename (the three wrapper functions below all provide one); sometimes you might just want pure randomness with no meaning attached, and leaving unique_name out entirely still works.

# python
#     return os.path.join(subfolder, f"{name}{ext}")

# Glues the folder and the final filename (name + ext, e.g. "user_5_1699999999" + ".jpg") together into one proper path, using os.path.join so it works correctly regardless of operating system.

# 4. avatar_upload_path
# python
# def avatar_upload_path(instance, filename):

# Django will always call this with exactly these two arguments (the model instance being saved, and the original filename) — this is Django's own calling convention for upload_to=, not something we chose.

# python
#     subfolder = os.path.join("companies", str(instance.company_id), "avatars")
# instance.company_id — reads the actual company ID off the specific user being saved right now. This is instance finally being put to use — pulling real, specific information out of the object Django handed us.
# str(...) — company IDs are likely stored as UUIDs (actual UUID objects, not text) or numbers internally; wrapping in str() guarantees we get plain text, since os.path.join needs text pieces, not raw UUID objects.
# The result: something like "companies/9f8a.../avatars" — every user's avatar automatically sorted into their own company's folder.
# python
#     unique_name = f"user_{instance.id}_{int(time.time())}"
# instance.id — the specific user's own ID, so the filename is always tied to that exact user, not shared with anyone else.
# time.time() — asks "what time is it right now?", returned as a number.
# int(...) — chops off the decimal fraction, leaving a clean whole number like 1754345678.
# The f-string glues it all together: "user_5_1754345678" — unique to this user, and unique to this specific moment they uploaded.
# python
#     return generic_upload_path(subfolder, filename, unique_name=unique_name)

# Hands everything off to the shared engine — the folder we just built, the original filename (only used here to steal its extension), and our specific chosen name.

# 5. The two logo functions
# python
# def company_logo_light_upload_path(instance, filename):
#     subfolder = os.path.join("companies", str(instance.id), "logos")
#     unique_name = f"light_{int(time.time())}"
#     return generic_upload_path(subfolder, filename, unique_name=unique_name)

# Nearly identical shape to avatar_upload_path, with two differences:

# Here, instance is the company itself (not a user belonging to a company), so it uses instance.id directly rather than instance.company_id.
# The unique_name is just "light_<timestamp>" — no user ID involved, since a company only has one light logo, not one per user.

# company_logo_dark_upload_path is the exact same idea, just labeled "dark" instead of "light", and saving to the same logos folder — so a company's light and dark logos end up sitting right next to each other.

# import os
# import uuid

# def generic_upload_path(instance, filename, subfolder):
#     _, ext = os.path.splitext(filename)
#     filename = f"{uuid.uuid4()}{ext.lower()}"
#     return os.path.join(subfolder, filename)

# def avatar_upload_path(instance, filename):
#     return generic_upload_path(
#         instance,
#         filename,
#         "avatars",
#     )
    
# def company_logo_light_upload_path(instance, filename):
#     return generic_upload_path(
#         instance,
#         filename,
#         "company/logos/light",
#     )
    
# def company_logo_dark_upload_path(instance, filename):
#     return generic_upload_path(
#         instance,
#         filename,
#         "company/logos/dark",
#     )