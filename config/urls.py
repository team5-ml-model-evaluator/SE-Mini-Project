from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect
from django.urls import include, path

from .views import admin_dashboard, register


@login_required
def dashboard(request):
    return redirect("dataset_list")


urlpatterns = [
    path("admin/", admin.site.urls),
    path("register/", register, name="register"),
    path(
        "login/",
        auth_views.LoginView.as_view(
            template_name="registration/login.html"
        ),
        name="login",
    ),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("admin-dashboard/", admin_dashboard, name="admin_dashboard"),
    path("dashboard/", dashboard, name="dashboard"),
    path("", include("webui.urls")),
]