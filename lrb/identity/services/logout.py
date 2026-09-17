def logout():
    """
    Session-based logout has no server-side token to invalidate — the actual
    session teardown happens via django.contrib.auth.logout(request) in the
    GraphQL mutation, since only the mutation has access to the request object.
    This function exists as a layering placeholder in case future session
    bookkeeping (e.g. an audit log entry) is added here.
    """
    return True