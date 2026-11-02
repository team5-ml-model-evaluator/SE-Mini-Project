from django.urls import path

from . import views

urlpatterns = [
    path("admin/catalogue/", views.catalogue_list, name="catalogue_list"),
    path("admin/catalogue/<uuid:pk>/delete/", views.catalogue_delete, name="catalogue_delete"),
]
