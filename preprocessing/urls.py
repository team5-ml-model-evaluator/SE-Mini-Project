from django.urls import path

from . import views

urlpatterns = [
    path("datasets/<uuid:pk>/preprocessing/", views.configure, name="preprocessing_configure"),
]
