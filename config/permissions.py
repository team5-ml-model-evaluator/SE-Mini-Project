
from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def role_required(*group_names):
    """Restrict a view to users in specified groups or superusers."""

    if not group_names:
        raise ValueError("At least one role/group name must be provided.")

    def decorator(view_func):
        @login_required
        @wraps(view_func)
        def wrapped_view(request, *args, **kwargs):
            user = request.user

            if user.is_superuser or user.groups.filter(
                name__in=group_names
            ).exists():
                return view_func(request, *args, **kwargs)

            raise PermissionDenied(
                "You do not have permission to access this page."
            )

        return wrapped_view

    return decorator
