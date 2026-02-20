from django.urls import path
from . import views


# Regular urls

urlpatterns = [
    path("", views.page_list, name="page_list"),
    path("pages/<slug:slug>/", views.page_detail, name="page_detail"),
]

# Function / Tracking stuff

urlpatterns += [
    path("track/event/", views.track_event, name="track_event"),
]



# Dashboartd Pages

urlpatterns += [
    path("dashboard/", views.dashboard_home, name="dashboard_home"),
    path("dashboard/pages/<slug:page_slug>/", views.dashboard_page_detail, name="dashboard_page_detail"),
]