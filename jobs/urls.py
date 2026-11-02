
from django.urls import path

from . import views


urlpatterns = [
    path(
        "jobs/create/",
        views.create_training_job,
        name="create_training_job",
    ),
    path(
        "jobs/",
        views.list_training_jobs,
        name="training_job_list",
    ),
    path(
        "jobs/<uuid:job_id>/status/",
        views.training_job_status,
        name="training_job_status",
    ),
]
