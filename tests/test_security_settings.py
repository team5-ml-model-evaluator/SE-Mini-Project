import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from django.conf import settings
from django.test import override_settings
from django.urls import reverse


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def load_settings_with_environment(**overrides):
    environment = os.environ.copy()
    for name in (
        "SECURE_SSL_REDIRECT",
        "SESSION_COOKIE_SECURE",
        "CSRF_COOKIE_SECURE",
        "SECURE_HSTS_SECONDS",
        "SECURE_HSTS_INCLUDE_SUBDOMAINS",
        "TRUST_X_FORWARDED_PROTO",
        "CSRF_TRUSTED_ORIGINS",
    ):
        environment.pop(name, None)
    environment.update(overrides)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import json; import config.settings as s; "
                "print(json.dumps({"
                "'debug': s.DEBUG, "
                "'redirect': s.SECURE_SSL_REDIRECT, "
                "'session_cookie': s.SESSION_COOKIE_SECURE, "
                "'csrf_cookie': s.CSRF_COOKIE_SECURE, "
                "'hsts_seconds': s.SECURE_HSTS_SECONDS, "
                "'hsts_subdomains': s.SECURE_HSTS_INCLUDE_SUBDOMAINS, "
                "'proxy_header': getattr(s, 'SECURE_PROXY_SSL_HEADER', None), "
                "'csrf_origins': s.CSRF_TRUSTED_ORIGINS"
                "}))"
            ),
        ],
        capture_output=True,
        check=True,
        cwd=PROJECT_ROOT,
        env=environment,
        text=True,
    )
    return json.loads(result.stdout)


def test_development_disables_https_redirect_and_hsts():
    configuration = load_settings_with_environment(
        DJANGO_DEBUG="1",
        SECURE_HSTS_SECONDS="31536000",
        SECURE_HSTS_INCLUDE_SUBDOMAINS="1",
    )

    assert configuration == {
        "debug": True,
        "redirect": False,
        "session_cookie": False,
        "csrf_cookie": False,
        "hsts_seconds": 0,
        "hsts_subdomains": False,
        "proxy_header": None,
        "csrf_origins": [],
    }


def test_production_environment_enables_secure_settings_and_trusted_origins():
    configuration = load_settings_with_environment(
        DJANGO_DEBUG="0",
        DJANGO_SECRET_KEY="test-only-secret",
        DJANGO_ALLOWED_HOSTS="evaluator.example.test",
        SECURE_SSL_REDIRECT="1",
        SESSION_COOKIE_SECURE="true",
        CSRF_COOKIE_SECURE="yes",
        SECURE_HSTS_SECONDS="31536000",
        SECURE_HSTS_INCLUDE_SUBDOMAINS="1",
        TRUST_X_FORWARDED_PROTO="true",
        CSRF_TRUSTED_ORIGINS="https://evaluator.example.test, https://admin.example.test",
    )

    assert configuration == {
        "debug": False,
        "redirect": True,
        "session_cookie": True,
        "csrf_cookie": True,
        "hsts_seconds": 31536000,
        "hsts_subdomains": True,
        "proxy_header": ["HTTP_X_FORWARDED_PROTO", "https"],
        "csrf_origins": [
            "https://evaluator.example.test",
            "https://admin.example.test",
        ],
    }


@pytest.mark.django_db
@override_settings(SECURE_SSL_REDIRECT=True, SECURE_PROXY_SSL_HEADER=None)
def test_http_request_redirects_to_https_even_with_untrusted_forwarded_header(client):
    response = client.get(
        reverse("login"),
        HTTP_X_FORWARDED_PROTO="https",
    )

    assert response.status_code == 301
    assert response["Location"] == f"https://testserver{reverse('login')}"


@pytest.mark.django_db
@override_settings(SECURE_SSL_REDIRECT=False)
def test_http_redirect_is_disabled_in_development(client):
    response = client.get(reverse("login"))

    assert response.status_code == 200


@pytest.mark.django_db
@override_settings(
    SECURE_SSL_REDIRECT=True,
    SECURE_PROXY_SSL_HEADER=("HTTP_X_FORWARDED_PROTO", "https"),
)
def test_explicitly_trusted_proxy_header_marks_request_secure(client):
    response = client.get(
        reverse("login"),
        HTTP_X_FORWARDED_PROTO="https",
    )

    assert response.status_code == 200


def test_existing_local_settings_keep_security_headers_and_cookie_policy():
    assert settings.SESSION_COOKIE_HTTPONLY is True
    assert settings.SESSION_COOKIE_SAMESITE == "Lax"
    assert settings.CSRF_COOKIE_SAMESITE == "Lax"
    assert settings.X_FRAME_OPTIONS == "DENY"
    assert settings.SECURE_CONTENT_TYPE_NOSNIFF is True
    assert settings.SECURE_REFERRER_POLICY == "strict-origin-when-cross-origin"
