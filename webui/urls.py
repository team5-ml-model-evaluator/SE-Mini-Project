from django.urls import path

from . import views

urlpatterns = [
    path("", views.dataset_list, name="dataset_list"),
    path("datasets/new/", views.dataset_new, name="dataset_new"),
    path("datasets/<uuid:pk>/", views.dataset_detail, name="dataset_detail"),
    path("datasets/<uuid:pk>/pipeline/", views.pipeline_step, name="pipeline_step"),
    path("datasets/<uuid:pk>/model/", views.model_step, name="model_step"),
    path("datasets/<uuid:pk>/summary/", views.settings_summary, name="settings_summary"),
]
