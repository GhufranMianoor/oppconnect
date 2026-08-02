from django.db.models import Q

from .models import Notification, TeamMembership


def team_context(request):
    if request.user.is_authenticated:
        memberships = list(
            TeamMembership.objects.filter(user=request.user).select_related("team").order_by("joined_at")
        )
        team = None
        if memberships:
            active_id = request.session.get("active_team_id")
            team = next((m.team for m in memberships if m.team_id == active_id), None) or memberships[0].team
        q = Q(user=request.user)
        if team:
            q |= Q(team=team)
        unread = Notification.objects.filter(q, is_read=False).count()
        return {
            "my_team": team,
            "my_teams": [m.team for m in memberships],
            "unread_count": unread,
        }
    return {}
