
from django.contrib import messages
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import Group
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods, require_POST

from .permissions import role_required

from webui.audit import record_audit
from webui.models import AuditLog, Dataset, Run, RunBatch


@role_required("Admin")
def admin_dashboard(request):
    """Display a page accessible only to administrators."""
    user_model = get_user_model()
    return render(
        request,
        "webui/admin_dashboard.html",
        {
            "active_users": user_model.objects.filter(is_active=True).count(),
            "deactivated_users": user_model.objects.filter(is_active=False).count(),
            "total_users": user_model.objects.count(),
            "total_datasets": Dataset.objects.count(),
            "total_runs": Run.objects.count(),
            "total_batches": RunBatch.objects.count(),
            "total_audit_events": AuditLog.objects.count(),
        },
    )


@role_required("Admin")
def admin_datasets(request):
    """Show dataset metadata and ownership, never the uploaded file contents."""
    datasets = Dataset.objects.select_related("owner").order_by("-created_at")
    return render(
        request,
        "webui/admin_datasets.html",
        {"datasets": datasets},
    )


@role_required("Admin")
def admin_users(request):
    """List and search accounts without exposing password data to the template."""
    user_model = get_user_model()
    query = request.GET.get("q", "").strip()[:255]
    users = user_model.objects.only(
        "pk", "username", "email", "is_active", "is_superuser"
    )
    if query:
        users = users.filter(
            Q(username__icontains=query) | Q(email__icontains=query)
        )
    return render(
        request,
        "webui/admin_users.html",
        {"accounts": users.order_by("username"), "query": query},
    )


@role_required("Admin")
@require_POST
def set_account_status(request, user_id, action):
    """Activate or deactivate an account; never delete users or alter superusers."""
    if action not in {"deactivate", "reactivate"}:
        raise Http404

    user_model = get_user_model()
    with transaction.atomic():
        target = get_object_or_404(
            user_model.objects.select_for_update(), pk=user_id
        )
        if target.is_superuser:
            raise PermissionDenied("Superuser account status is protected.")
        if target.pk == request.user.pk and action == "deactivate":
            raise PermissionDenied("You cannot deactivate your own account.")

        is_active = action == "reactivate"
        if target.is_active != is_active:
            target.is_active = is_active
            target.save(update_fields=["is_active"])
            record_audit(
                actor=request.user,
                action={
                    "deactivate": "account_deactivated",
                    "reactivate": "account_reactivated",
                }[action],
                resource=f"user:{target.pk}",
                outcome="success",
                details={"username": target.get_username()},
            )
            status = "reactivated" if is_active else "deactivated"
            messages.success(request, f"Account {target.get_username()} {status}.")
        else:
            messages.info(
                request,
                f"Account {target.get_username()} is already "
                f"{'active' if is_active else 'deactivated'}.",
            )

    return redirect("admin_users")


@require_http_methods(["GET", "POST"])
def register(request):
    """Register a new user and assign the default User role."""
    if request.user.is_authenticated:
        return redirect("dashboard")

    if request.method == "POST":
        form = UserCreationForm(request.POST)

        if form.is_valid():
            user = form.save()
            user_group, _ = Group.objects.get_or_create(name="User")
            user.groups.add(user_group)

            record_audit(
                actor=user ,
                action="user_registration" ,
                resource=f"user:{user.pk}" ,
                outcome="success" ,
            )

            return redirect("login")
    else:
        form = UserCreationForm()

    return render(
        request,
        "registration/register.html",
        {"form": form},
    )
