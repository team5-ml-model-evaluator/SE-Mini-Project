
import json

import pytest
from django.contrib.auth.models import User
from django.urls import reverse

from jobs.models import TrainingJob


PASSWORD = "TestPassword!7392"


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username="jobuser",
        password=PASSWORD,
    )


@pytest.fixture
def other_user(db):
    return User.objects.create_user(
        username="otheruser",
        password=PASSWORD,
    )


@pytest.fixture
def authenticated_client(client, user):
    client.force_login(user)
    return client


@pytest.mark.django_db
def test_create_training_job(authenticated_client, user):
    response = authenticated_client.post(
        reverse("create_training_job"),
        {
            "dataset_name": "sample.csv",
            "model_name": "RandomForestClassifier",
            "configuration": '{"random_state": 42}',
        },
    )

    assert response.status_code == 200

    job = TrainingJob.objects.get(user=user)
    assert job.dataset_name == "sample.csv"
    assert job.model_name == "RandomForestClassifier"
    assert job.status == TrainingJob.Status.QUEUED
    assert job.configuration == {"random_state": 42}


@pytest.mark.django_db
def test_job_list_shows_only_current_users_jobs(
    authenticated_client, user, other_user
):
    own_job = TrainingJob.objects.create(
        user=user,
        dataset_name="mine.csv",
        model_name="LogisticRegression",
    )
    other_job = TrainingJob.objects.create(
        user=other_user,
        dataset_name="other.csv",
        model_name="LinearRegression",
    )

    response = authenticated_client.get(
        reverse("training_job_list")
    )

    assert response.status_code == 200
    assert own_job in response.context["jobs"]
    assert other_job not in response.context["jobs"]


@pytest.mark.django_db
def test_status_endpoint_returns_job_status(
    authenticated_client, user
):
    job = TrainingJob.objects.create(
        user=user,
        dataset_name="sample.csv",
        model_name="DecisionTreeClassifier",
    )

    response = authenticated_client.get(
        reverse("training_job_status", kwargs={"job_id": job.id})
    )

    assert response.status_code == 200
    data = json.loads(response.content)
    assert data["id"] == str(job.id)
    assert data["status"] == TrainingJob.Status.QUEUED


@pytest.mark.django_db
def test_user_cannot_access_another_users_job_status(
    authenticated_client, other_user
):
    other_job = TrainingJob.objects.create(
        user=other_user,
        dataset_name="private.csv",
        model_name="LinearRegression",
    )

    response = authenticated_client.get(
        reverse(
            "training_job_status",
            kwargs={"job_id": other_job.id},
        )
    )

    assert response.status_code == 404


@pytest.mark.django_db
def test_unauthenticated_user_cannot_create_job(client):
    response = client.get(reverse("create_training_job"))

    assert response.status_code == 302
    assert "/login/" in response.url


@pytest.mark.django_db
def test_invalid_model_choice_does_not_create_job(
    authenticated_client, user
):
    response = authenticated_client.post(
        reverse("create_training_job"),
        {
            "dataset_name": "sample.csv",
            "model_name": "UnknownModel",
            "configuration": "{}",
        },
    )

    assert response.status_code == 200
    assert not TrainingJob.objects.filter(user=user).exists()
