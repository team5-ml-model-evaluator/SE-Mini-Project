from django.urls import path

from . import views

urlpatterns = [
    path("", views.dataset_list, name="dataset_list"),
    path("datasets/new/", views.dataset_new, name="dataset_new"),
    path("datasets/<uuid:pk>/", views.dataset_detail, name="dataset_detail"),
    path("datasets/<uuid:pk>/pipeline/", views.pipeline_step, name="pipeline_step"),
    path("datasets/<uuid:pk>/model/", views.model_step, name="model_step"),
    path("datasets/<uuid:pk>/summary/", views.settings_summary, name="settings_summary"),
    path("datasets/<uuid:pk>/run/", views.start_run, name="start_run"),
    path("runs/<str:job_key>/", views.run_detail, name="run_detail"),
    path("api/runs/<str:job_key>/status", views.run_status, name="run_status"),
]
