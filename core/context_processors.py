from .models import TeamMembership


def team_context(request):
    if request.user.is_authenticated:
        membership = TeamMembership.objects.filter(user=request.user).select_related("team").first()
        team = membership.team if membership else None
        unread = team.notifications.filter(is_read=False).count() if team else 0
        return {"my_team": team, "unread_count": unread}
    return {}
