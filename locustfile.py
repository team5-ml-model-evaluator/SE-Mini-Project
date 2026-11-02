import os
import re

from locust import HttpUser, task, between


class MLModelEvaluatorUser(HttpUser):
    wait_time = between(1, 3)

    def on_start(self):
        username = os.getenv("LOCUST_USERNAME")
        password = os.getenv("LOCUST_PASSWORD")

        if not username or not password:
            raise RuntimeError(
                "Set LOCUST_USERNAME and LOCUST_PASSWORD before running Locust."
            )

        # Load login page and obtain CSRF token.
        response = self.client.get("/login/", name="GET /login")

        match = re.search(
            r'<input\b(?=[^>]*\bname=["\']csrfmiddlewaretoken["\'])'
            r'(?=[^>]*\bvalue=["\']([^"\']+)["\'])[^>]*>' ,
            response.text ,
        )

        if not match:
            raise RuntimeError("Could not find CSRF token on login page.")

        csrf_token = match.group(1)

        # Authenticate this simulated user.
        response = self.client.post(
            "/login/",
            {
                "username": username,
                "password": password,
                "csrfmiddlewaretoken": csrf_token,
            },
            headers={"Referer": self.host + "/login/"},
            name="POST /login",
            allow_redirects=False,
        )

        if response.status_code not in (302, 303):
            raise RuntimeError(
                "Locust login failed. Check the test account credentials."
            )

    @task(5)
    def dataset_list(self):
        self.client.get("/", name="GET /")

    @task(3)
    def upload_page(self):
        self.client.get("/datasets/new/", name="GET /datasets/new/")

    @task(2)
    def login_page(self):
        self.client.get("/login/", name="GET /login")