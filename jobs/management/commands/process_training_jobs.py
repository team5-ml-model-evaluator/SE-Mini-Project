
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from jobs.models import TrainingJob


def execute_training_job(job):
    """
    Placeholder for the model-training executor.

    The later model-execution task must replace this implementation
    with actual dataset loading, preprocessing, and model training.
    """
    raise NotImplementedError(
        "Model training is not integrated yet. "
        "Implement the training executor before processing real jobs."
    )


class Command(BaseCommand):
    help = "Process queued training jobs outside web requests."

    def add_arguments(self, parser):
        parser.add_argument(
            "--once",
            action="store_true",
            help="Process at most one queued job, then exit.",
        )

    def _claim_next_job(self):
        """Atomically claim a queued job so workers do not claim it twice."""
        while True:
            job_id = (
                TrainingJob.objects.filter(
                    status=TrainingJob.Status.QUEUED
                )
                .order_by("created_at")
                .values_list("id", flat=True)
                .first()
            )

            if job_id is None:
                return None

            with transaction.atomic():
                claimed = TrainingJob.objects.filter(
                    id=job_id,
                    status=TrainingJob.Status.QUEUED,
                ).update(
                    status=TrainingJob.Status.RUNNING,
                    started_at=timezone.now(),
                    error_message="",
                )

            if claimed == 1:
                return job_id

    def _mark_failed(self, job, message):
        job.status = TrainingJob.Status.FAILED
        job.error_message = message[:5000]
        job.finished_at = timezone.now()
        job.save(
            update_fields=[
                "status",
                "error_message",
                "finished_at",
                "updated_at",
            ]
        )

    def handle(self, *args, **options):
        processed = 0

        while True:
            job_id = self._claim_next_job()

            if job_id is None:
                if processed == 0:
                    self.stdout.write("No queued training jobs.")
                return

            job = TrainingJob.objects.get(id=job_id)
            self.stdout.write(f"Processing job {job.id}...")

            try:
                execute_training_job(job)
            except Exception as exc:
                self._mark_failed(
                    job,
                    f"{type(exc).__name__}: {exc}",
                )
                self.stderr.write(
                    self.style.WARNING(
                        f"Job {job.id} failed: {job.error_message}"
                    )
                )
            else:
                job.status = TrainingJob.Status.COMPLETED
                job.finished_at = timezone.now()
                job.error_message = ""
                job.save(
                    update_fields=[
                        "status",
                        "finished_at",
                        "error_message",
                        "updated_at",
                    ]
                )
                self.stdout.write(
                    self.style.SUCCESS(f"Job {job.id} completed.")
                )

            processed += 1

            if options["once"]:
                return
