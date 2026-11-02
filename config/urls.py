from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.urls import include, path

from .views import (
    admin_dashboard,
    admin_datasets,
    admin_users,
    register,
    set_account_status,
)

from config.auth_views import AuditLoginView


@login_required
def dashboard(request):
    return redirect("dataset_list")


urlpatterns = [
    path("admin/", admin.site.urls),
    path("register/", register, name="register"),
    path(
        "login/",
        AuditLoginView.as_view(
            template_name="registration/login.html"
        ),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("admin-dashboard/", admin_dashboard, name="admin_dashboard"),
    path("admin-dashboard/users/", admin_users, name="admin_users"),
    path(
        "admin-dashboard/users/<int:user_id>/<str:action>/",
        set_account_status,
        name="admin_user_status",
    ),
    path("admin-dashboard/datasets/", admin_datasets, name="admin_datasets"),
    path("dashboard/", dashboard, name="dashboard"),
    path("", include("jobs.urls")),
    path("", include("webui.urls")),
]