from django.contrib.auth import views as auth_views
from django.urls import include, path

urlpatterns = [
    # STAND-IN: login/logout until AccountsApp (MLE-F-001..003) is merged.
    path("accounts/login/", auth_views.LoginView.as_view(), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("", include("webui.urls")),
    path("preprocessing/", include("preprocessing.urls")),
]
