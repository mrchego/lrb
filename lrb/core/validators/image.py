from django.core.exceptions import ValidationError
import os
from lrb.core.constants import ALLOWED_IMAGE_EXTENSIONS, MAX_IMAGE_SIZE_MB


def validate_image_size(image):
    if image.size > MAX_IMAGE_SIZE_MB * 1024 * 1024:
        raise ValidationError(f"Image size must be less than {MAX_IMAGE_SIZE_MB}MB.")
    return image


def validate_image_extension(filename):
    ext = os.path.splitext(filename)[1].lower()
    if ext not in ALLOWED_IMAGE_EXTENSIONS:
        raise ValidationError(f"Image extension {ext} is not allowed.")
    return filename

# 1. Purpose (why this exists)

# When users upload images (profile pictures, company logos, product photos), you can't just trust whatever file arrives — someone could upload a 500MB file that fills up your server's disk, or a .exe file renamed to look like an image, or a file format your app has no way to display properly. These two functions are the safety checks that run before an uploaded image is accepted: one checks the file isn't too big, the other checks the file type is actually one you allow.

# 2. The imports
# python
# from django.core.exceptions import ValidationError

# Same tool you've now seen three times — Django's standard "this input is invalid" error.

# python
# import os

# os is a built-in Python toolbox for talking to the operating system — file paths, folders, environment variables. Here, we only need one small piece of it: figuring out a file's extension (like .png or .jpg) from its filename.

# python
# from lrb.core.constants import ALLOWED_IMAGE_EXTENSIONS, MAX_IMAGE_SIZE_MB

# Same pattern as DEFAULT_PAGE_SIZE/MAX_PAGE_SIZE earlier — pulling shared, named values from your one central constants file, rather than hardcoding numbers or lists directly here. ALLOWED_IMAGE_EXTENSIONS is probably something like [".jpg", ".jpeg", ".png", ".webp"], and MAX_IMAGE_SIZE_MB is probably a plain number, like 5.

# 3. validate_image_size
# python
# def validate_image_size(image):

# One input, image — this is expected to be a Django "uploaded file" object (the kind you get automatically when a user submits a file through a form or API), not just raw bytes or a filename.

# python
#     if image.size > MAX_IMAGE_SIZE_MB * 1024 * 1024:
# image.size — Django file objects automatically carry a .size property, telling you the file's size in bytes (the smallest unit computers measure data in).
# MAX_IMAGE_SIZE_MB * 1024 * 1024 — your constant is stored in megabytes (MB) — a human-friendly unit — but image.size is in bytes, a much smaller unit. To compare them fairly, you have to convert megabytes into bytes. There are 1024 bytes in a kilobyte, and 1024 kilobytes in a megabyte — so multiplying by 1024 * 1024 converts your MAX_IMAGE_SIZE_MB (say, 5) into the equivalent number of bytes (5,242,880). Without this conversion, you'd be comparing two numbers in completely different units — like comparing "5 miles" to "5 feet" without converting first.
# python
#         raise ValidationError(f"Image size must be less than {MAX_IMAGE_SIZE_MB}MB.")

# If the file is too big, stop and complain — with a message that plugs the actual limit into the text using an f-string, so if MAX_IMAGE_SIZE_MB ever changes, this message automatically stays accurate without you having to edit it by hand.

# Notice: no return statement, and no try/except at all. This function either raises an error (image too big) or does nothing and quietly finishes (image is fine) — it doesn't hand back a value like validate_uuid and validate_email did. That's a real, deliberate difference worth flagging — I'll come back to it in the design question below.

# 4. validate_image_extension
# python
# def validate_image_extension(filename):

# One input — this time, just the plain filename text (like "vacation_photo.PNG"), not the whole file object.

# python
#     ext = os.path.splitext(filename)[1].lower()

# Three steps happening on one line, inside-out:

# os.path.splitext(filename) — this os tool splits a filename into two pieces: the name and the extension. E.g., os.path.splitext("vacation_photo.PNG") gives you back ("vacation_photo", ".PNG") — a pair of two values (Python calls this a "tuple," same concept as the accidental-tuple bug we found earlier, but used correctly and on purpose here).
# [1] — grabs just the second item from that pair (position 1, since counting starts at 0 in Python) — meaning just the extension, ".PNG".
# .lower() — converts that text to all-lowercase, turning .PNG into .png. This matters because file extensions can arrive in any capitalization (.PNG, .Png, .png are all the same file type to a human, but different pieces of text to a computer) — without this, someone uploading a .PNG file might get incorrectly rejected if your allowed list only contains lowercase .png.
# python
#     if ext not in ALLOWED_IMAGE_EXTENSIONS:

# Checks: is this extension not present in your allowed list? (ALLOWED_IMAGE_EXTENSIONS is presumably a list like [".jpg", ".jpeg", ".png", ".webp"].)

# python
#         raise ValidationError(f"Image extension {ext} is not allowed.")

# If it's not on the list, stop and complain, naming the specific bad extension in the message.

# DIY — How to Build Your Own "File Upload Validator"

# If you ever need to validate a different kind of upload (a PDF resume, a CSV import, a video file), here's the recipe, based on the pattern these two functions establish:

# Split "is this thing safe/allowed" into separate, single-purpose checks — don't write one giant function checking size AND type AND anything else all at once. validate_image_size and validate_image_extension are deliberately two small functions, not one. This means each can be reused independently (e.g., maybe some upload only cares about size, not extension) and each is easy to test on its own.
# Store your limits and allowed lists as named constants, never hardcoded numbers/strings inside the validator itself — exactly like MAX_IMAGE_SIZE_MB and ALLOWED_IMAGE_EXTENSIONS living in constants.py.
# Know which property you actually need from the upload, and pick your function's input accordingly:
# Need the file's size, content, or type? → accept the whole file object (like validate_image_size(image) does).
# Only need the filename text? → just accept the filename string (like validate_image_extension(filename) does) — simpler, and doesn't require the whole file object if you don't need it.
# Always do any necessary unit conversions or text-normalizing explicitly and clearly (bytes vs. megabytes, uppercase vs. lowercase) — don't assume the raw data arrives already in the shape you need.
# Raise ValidationError with a specific, useful message — always explain what was wrong and, where possible, what the limit actually is, using an f-string so the message can't drift out of sync with your actual constants.