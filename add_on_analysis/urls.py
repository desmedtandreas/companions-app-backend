from django.urls import path
from add_on_analysis import views

app_name = "add_on_analysis"
urlpatterns = [
    path("", views.vertex_overview, name="vertex_overview"),
    path("<str:vertex_name>/addons/", views.addon_overview, name="addon_overview"),
    path("<str:vertex_name>/addons/upload", views.upload_file, name="upload_file"),
    path("delete/<int:id>/", views.delete_addon, name="delete_addon"),
    path("<str:vertex_name>/export/", views.export_addons, name="export_addons"),
]