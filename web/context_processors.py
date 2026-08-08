from .decorators import is_admin_user


def role_context(request):
    is_authenticated = request.user.is_authenticated
    is_admin = False
    username = ''

    if is_authenticated:
        is_admin = is_admin_user(request.user)
        username = request.user.username

    return {
        'nav_is_authenticated': is_authenticated,
        'nav_is_admin': is_admin,
        'nav_username': username,
    }
