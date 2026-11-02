
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import Group
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from .permissions import role_required

from webui.audit import record_audit

@role_required("Admin")
def admin_dashboard(request):
    """Display a page accessible only to administrators."""
    return HttpResponse(
        "Administrator access granted. "
        "You can manage the ML Model Evaluator."
    )


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
