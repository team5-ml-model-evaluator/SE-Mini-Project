"""Internal child-process entry point for a supervised model-training run."""

from django.core.management.base import BaseCommand, CommandError

from webui.models import Run
from webui.standins.runs import _execute_in_worker


class Command(BaseCommand):
    help = "Execute one queued model run (internal worker command)."

    def add_arguments(self, parser):
        parser.add_argument("--job-key", required=True)
        parser.add_argument("--queue-seconds", type=float, default=0)
        parser.add_argument("--run-seconds", type=float, default=0)

    def handle(self, *args, **options):
        job_key = options["job_key"]

        if not Run.objects.filter(job_key=job_key).exists():
            raise CommandError(
                "The requested training run does not exist."
            )

        _execute_in_worker(
            job_key,
            queue_s=options["queue_seconds"],
            run_s=options["run_seconds"],
        )
