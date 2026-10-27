
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
]
