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

        team_ids = [m.team_id for m in memberships]
        personal_unread = Notification.objects.filter(user=request.user, is_read=False).count()
        team_unread = 0
        if team_ids:
            # Team-wide notifications track read state per-player (read_by),
            # not a single shared is_read flag - otherwise one teammate
            # opening their notifications would mark them read for everyone.
            team_unread = Notification.objects.filter(
                team_id__in=team_ids, user__isnull=True
            ).exclude(read_by=request.user).count()
        unread = personal_unread + team_unread
        return {
            "my_team": team,
            "my_teams": [m.team for m in memberships],
            "unread_count": unread,
        }
    return {}