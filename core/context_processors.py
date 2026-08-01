from django.db.models import Q

from .models import Notification, TeamMembership


def team_context(request):
    if request.user.is_authenticated:
        membership = TeamMembership.objects.filter(user=request.user).select_related("team").first()
        team = membership.team if membership else None
        q = Q(user=request.user)
        if team:
            q |= Q(team=team)
        unread = Notification.objects.filter(q, is_read=False).count()
        return {"my_team": team, "unread_count": unread}
    return {}
