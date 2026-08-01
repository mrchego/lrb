import uuid
from django.core.exceptions import ValidationError

def validate_uuid(value):
    try:
        uuid.UUID(str(value))
    except(ValueError, TypeError):
        raise ValidationError("Invalid UUID format")
    return value


# 1. Purpose (why this exists)

# Your project identifies things (users, roles, companies) with UUIDs instead of simple numbers — a UUID looks like 550e8400-e29b-41d4-a716-446655440000. When someone sends your app a UUID (say, "give me the user with this ID"), that input arrives as plain text — the computer doesn't automatically know if that text is actually a real UUID or just random garbage someone typed. This function's whole job: check "is this text actually shaped like a real UUID?" If yes, let it through. If no, stop everything and complain clearly, before the bad data goes any further into your system.

# 2. Imports — explained like you've never coded
# python
# import uuid

# import means "bring in a toolbox that's not part of the basic Python language, but that someone already built." uuid is a toolbox built into Python itself (you don't need to install anything extra) — it contains tools specifically for creating and checking UUIDs. Without this line, the word uuid would mean nothing later in the file — Python would say "I don't know what that is."

# python
# from django.core.exceptions import ValidationError

# This says: "from the Django framework, specifically from its core.exceptions toolbox, bring in just the one tool called ValidationError." ValidationError is a pre-built way of saying "the data you gave me is invalid" in a way Django understands and knows how to display nicely (e.g., in an admin form, it'll show a red error message under a field).

# 3. The function signature — explained piece by piece
# python
# def validate_uuid(value):
# def = "I am about to define a new function" (a function is a named, reusable block of instructions).
# validate_uuid = the name we're giving this function, so we can call it later by that name.
# (value) = this function expects to be handed one piece of input when it's used, and inside the function, we'll refer to that input using the name value. We don't know yet if value will be a proper UUID, a random string, a number, or even nothing at all — that's exactly what this function is about to check.
# 4. The body — line by line
# python
#     try:

# This means: "attempt to run the following lines, but be ready to catch it if something goes wrong instead of crashing the whole program."

# python
#         uuid.UUID(str(value))

# Two things happen here, inside out:

# str(value) — takes whatever value is (it might already be text, or it might be a number, or something else) and forces it into plain text form. E.g., if value was the number 123, str(123) gives you the text "123".
# uuid.UUID(...) — this is a tool from the uuid toolbox we imported. You hand it a piece of text, and it tries to build a real UUID object out of that text. If the text is properly shaped like a UUID, it succeeds quietly. If the text is garbage (like "hello"), this tool refuses and throws an error — which is exactly what we're catching below.
# python
#     except (ValueError, TypeError):

# except means "if something went wrong in the try block above, and it matches one of these specific problem-types, come here instead of crashing." (ValueError, TypeError) lists two different kinds of problems we're watching for:

# ValueError happens when the text exists and is a string, but its content is wrong shape (e.g., "hello" — it's a string, just not a UUID-looking one).
# TypeError happens when value was something so unusual that even str(value) couldn't produce something uuid.UUID() could work with — e.g., if value were None (Python's way of saying "nothing at all"), str(None) actually gives you the text "None", which then fails as a ValueError too, actually — so TypeError here is really a defensive extra net for stranger inputs.
# python
#         raise ValidationError("Invalid UUID format")

# raise means "stop everything, right now, and hand this problem up to whoever called this function." We're handing them a ValidationError (the tool we imported earlier) with the message "Invalid UUID format" — a human-readable explanation of what went wrong.

# python
#     return value

# If nothing went wrong above (the try block succeeded, no except was triggered), skip past the except entirely and reach this line: hand back the original value unchanged, as a signal of "yes, this was valid, here it is back."

# The one real design question worth understanding here

# This function raises Django's built-in ValidationError — not your project's own AppValidationError (from the exceptions file we just reviewed). That's a real, deliberate-or-accidental choice worth noticing: Django's own model fields (models.CharField(validators=[...])) specifically expect django.core.exceptions.ValidationError — so this function is clearly built to plug into a Django model field's validation, not directly into a GraphQL service.

# Question for you: if a GraphQL service (not a Django model) called validate_uuid() directly and it raised this Django ValidationError, would your GraphQL error-formatter (the one thing we said should only need to understand ApplicationError) know how to handle it? What do you think should happen instead — should the GraphQL service catch this and convert it, or should there be a second version of this validator for GraphQL use? -> The main idea to remember

# Each layer should speak its own language.

# Django layer → raises Django exceptions.
# Application service → catches Django exceptions and converts them into ApplicationError.
# GraphQL layer → only handles ApplicationError and turns it into a GraphQL response.

# This separation keeps your code cleaner, easier to maintain, and prevents the presentation layer (GraphQL) from depending on framework-specific implementation details.
