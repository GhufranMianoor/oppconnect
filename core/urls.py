from django.urls import path
from . import views

app_name = "core"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("onboard/", views.onboard_team, name="onboard_team"),
    path("availability/set/", views.set_availability, name="set_availability"),
    path("teams/", views.find_teams, name="find_teams"),
    path("teams/<int:pk>/", views.team_profile, name="team_profile"),
    path("teams/<int:pk>/request/", views.send_match_request, name="send_match_request"),
    path("teams/<int:pk>/join/", views.send_join_request, name="send_join_request"),
    path("teams/<int:pk>/message/", views.start_conversation, name="start_conversation"),
    path("my-team/", views.my_team, name="my_team"),
    path("requests/", views.match_requests, name="match_requests"),
    path("requests/create/", views.create_open_request, name="create_open_request"),
    path("requests/<int:pk>/<str:action>/", views.respond_request, name="respond_request"),
    path("join-requests/", views.team_join_requests, name="team_join_requests"),
    path("join-requests/<int:pk>/<str:action>/", views.respond_join_request, name="respond_join_request"),
    path("matches/", views.matches_list, name="matches"),
    path("matches/<int:pk>/", views.match_detail, name="match_detail"),
    path("matches/<int:pk>/submit-result/", views.submit_match_result, name="submit_match_result"),
    path("messages/", views.inbox, name="inbox"),
    path("messages/<int:pk>/", views.conversation_view, name="conversation"),
    path("notifications/", views.notifications_view, name="notifications"),
]
