
import pytest
from django.contrib.auth.models import Group, User


PASSWORD = "MLTest!7392Secure"


@pytest.mark.django_db
def test_registration_creates_user_and_assigns_default_role(client):
    response = client.post(
        "/register/",
        {
            "username": "newtestuser",
            "password1": PASSWORD,
            "password2": PASSWORD,
        },
    )

    assert response.status_code == 302
    assert response.url == "/login/"

    user = User.objects.get(username="newtestuser")
    assert user.check_password(PASSWORD)
    assert user.groups.filter(name="User").exists()


@pytest.mark.django_db
def test_user_can_log_in(client):
    User.objects.create_user(
        username="loginuser",
        password=PASSWORD,
    )

    response = client.post(
        "/login/",
        {
            "username": "loginuser",
            "password": PASSWORD,
        },
    )

    assert response.status_code == 302
    assert response.url == "/dashboard/"


@pytest.mark.django_db
def test_dashboard_requires_login(client):
    response = client.get("/")

    assert response.status_code == 302
    assert "/login/" in response.url


@pytest.mark.django_db
def test_regular_user_cannot_access_admin_dashboard(client):
    user = User.objects.create_user(
        username="regularuser",
        password=PASSWORD,
    )
    client.force_login(user)

    response = client.get("/admin-dashboard/")

    assert response.status_code == 403


@pytest.mark.django_db
def test_admin_group_can_access_admin_dashboard(client):
    user = User.objects.create_user(
        username="adminuser",
        password=PASSWORD,
    )
    admin_group, _ = Group.objects.get_or_create(name="Admin")
    user.groups.add(admin_group)
    client.force_login(user)

    response = client.get("/admin-dashboard/")

    assert response.status_code == 200
    assert b"Administrator access granted" in response.content
