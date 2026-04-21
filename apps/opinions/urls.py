from django.urls import path

from apps.opinions import views

app_name = "opinions"

urlpatterns = [
    path("<uuid:space_id>/nodes/<uuid:node_id>/opinion/", views.toggle_opinion, name="toggle_opinion"),
    path("<uuid:space_id>/posts/<uuid:post_id>/react/", views.toggle_reaction, name="toggle_reaction"),
]
