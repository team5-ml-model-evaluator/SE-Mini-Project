
from unittest.mock import patch

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command

from jobs.models import TrainingJob


@pytest.fixture
def user(db):
    return User.objects.create_user(
        username="worker_test_user",
        password="TestPassword!7392",
    )


@pytest.mark.django_db
def test_worker_marks_job_completed_after_success(user):
    job = TrainingJob.objects.create(
        user=user,
        dataset_name="sample.csv",
        model_name="RandomForestClassifier",
    )

    with patch(
        "jobs.management.commands.process_training_jobs.execute_training_job"
    ) as mock_executor:
        mock_executor.return_value = None

        call_command("process_training_jobs", once=True)

    job.refresh_from_db()

    assert job.status == TrainingJob.Status.COMPLETED
    assert job.started_at is not None
    assert job.finished_at is not None
    assert job.error_message == ""
    mock_executor.assert_called_once()


@pytest.mark.django_db
def test_worker_marks_job_failed_when_execution_raises(user):
    job = TrainingJob.objects.create(
        user=user,
        dataset_name="sample.csv",
        model_name="RandomForestClassifier",
    )

    with patch(
        "jobs.management.commands.process_training_jobs.execute_training_job"
    ) as mock_executor:
        mock_executor.side_effect = RuntimeError("Test training failure")

        call_command("process_training_jobs", once=True)

    job.refresh_from_db()

    assert job.status == TrainingJob.Status.FAILED
    assert job.started_at is not None
    assert job.finished_at is not None
    assert "Test training failure" in job.error_message


@pytest.mark.django_db
def test_worker_processes_one_job_with_once_option(user):
    job = TrainingJob.objects.create(
        user=user,
        dataset_name="sample.csv",
        model_name="LinearRegression",
    )

    with patch(
        "jobs.management.commands.process_training_jobs.execute_training_job"
    ) as mock_executor:
        call_command("process_training_jobs", once=True)

    job.refresh_from_db()

    assert job.status == TrainingJob.Status.COMPLETED
    mock_executor.assert_called_once()
