import factory
from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import make_password


User = get_user_model()


class UserFactory(factory.django.DjangoModelFactory):
    """
    Factory for creating test users.

    Creates users with unique email addresses and a hashed password.
    """

    class Meta:
        model = User

    # Identity
    email = factory.Sequence(
        lambda n: f"user{n}@example.com"
    )

    first_name = factory.Faker("first_name")
    last_name = factory.Faker("last_name")

    # Authentication
    password = factory.LazyFunction(
        lambda: make_password("TestPassword123!")
    )

    # Django authentication fields
    is_active = True
    is_staff = False
    is_superuser = False

    # Custom user fields
    is_email_verified = True
    can_login = True
    is_founder = False

    # Optional user information
    phone = ""
    company = None

    # Account security
    password_reset_required = False
    failed_login_attempts = 0
    last_password_change = None
    locked_until = None