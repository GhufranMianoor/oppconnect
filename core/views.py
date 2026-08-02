import calendar as cal

from django.contrib import messages as flash
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import (AvailabilityForm, MatchRequestForm, MessageForm,
                     OpenMatchRequestForm, PlayerMessageForm,
                     PlayerSearchForm, TeamForm, TeamJoinRequestForm,
                     TeamSearchForm)
from .models import (Availability, Conversation, Match, MatchGoal,
                      MatchRequest, Message, Notification, PlayerConversation,
                      PlayerRating, Team, TeamJoinRequest, TeamMembership)

User = get_user_model()


def get_user_teams(user):
    """Every team this user belongs to (as captain or player), name-sorted."""
    return Team.objects.filter(members__user=user).distinct().order_by("name")


def get_active_team(request):
    """
    The team currently 'in view' for this session. Since a player can now
    belong to several teams at once, we remember which one they last picked
    in the session and fall back to the earliest team they joined. Returns
    None if the user isn't on any team yet.
    """
    memberships = list(
        TeamMembership.objects.filter(user=request.user).select_related("team").order_by("joined_at")
    )
    if not memberships:
        return None
    active_id = request.session.get("active_team_id")
    if active_id:
        for m in memberships:
            if m.team_id == active_id:
                return m.team
    return memberships[0].team


def get_my_membership(user, team):
    if not team:
        return None
    return TeamMembership.objects.filter(user=user, team=team).first()


def build_convo_list(request, team):
    """
    Unified, most-recent-first list of every conversation this user can see:
    the active team's team-to-team conversations, plus this user's own
    player-to-player DM threads. Used for the messenger sidebar everywhere.
    """
    items = []
    if team:
        for c in Conversation.objects.filter(Q(team_a=team) | Q(team_b=team)).select_related("team_a", "team_b"):
            other = c.other(team)
            items.append({
                "kind": "team",
                "pk": c.pk,
                "name": other.name,
                "avatar_url": other.logo.url if other.logo else None,
                "last": c.last_message(),
            })
    for c in PlayerConversation.objects.filter(
        Q(player_a=request.user) | Q(player_b=request.user)
    ).select_related("player_a", "player_b"):
        other = c.other(request.user)
        items.append({
            "kind": "player",
            "pk": c.pk,
            "name": other.get_full_name() or other.username,
            "avatar_url": other.avatar.url if other.avatar else None,
            "last": c.last_message(),
        })
    items.sort(key=lambda x: x["last"].sent_at if x["last"] else timezone.now(), reverse=True)
    return items


@login_required
def onboard_team(request):
    """
    Create a team profile. Players can already belong to other teams (or
    even captain other teams) - this just adds one more, and makes it the
    active team for this session.
    """
    if request.method == "POST":
        form = TeamForm(request.POST, request.FILES)
        if form.is_valid():
            team = form.save(commit=False)
            team.captain = request.user
            team.save()
            TeamMembership.objects.create(team=team, user=request.user, role="captain")
            request.session["active_team_id"] = team.id
            flash.success(request, "Team profile created!")
            return redirect("core:dashboard")
    else:
        form = TeamForm()
    return render(request, "core/onboard_team.html", {"form": form})


@login_required
def set_active_team(request, pk):
    """
    Switch which of the player's teams is 'active' for this session. Not
    destructive (just a display preference), so - like logout_view above -
    a plain GET link is fine and sidesteps any POST/CSRF friction.
    """
    if TeamMembership.objects.filter(user=request.user, team_id=pk).exists():
        request.session["active_team_id"] = pk
    return redirect(request.META.get("HTTP_REFERER") or "core:dashboard")


@login_required
def dashboard(request):
    team = get_active_team(request)
    if not team:
        return redirect("core:onboard_team")

    pending_requests = MatchRequest.objects.filter(to_team=team, status="pending").select_related("from_team").order_by("proposed_date")[:5]

    nearby_teams = Team.objects.filter(city=team.city).exclude(id=team.id).order_by("-created_at")[:5]

    raw_matches = Match.objects.filter(Q(home_team=team) | Q(away_team=team), status="completed").select_related("home_team", "away_team").order_by("-date")[:5]
    recent_matches = [
        {
            "opponent": m.opponent_for(team),
            "date": m.date,
            "score": m.score_for(team),
            "result": m.result_for(team),
            "id": m.id,
        }
        for m in raw_matches
    ]

    today = timezone.localdate()
    month = int(request.GET.get("month", today.month))
    year = int(request.GET.get("year", today.year))
    cal.setfirstweekday(cal.MONDAY)
    month_days = cal.monthcalendar(year, month)
    avail_map = {a.date.day: a.status for a in Availability.objects.filter(team=team, date__year=year, date__month=month)}
    prev_month = month - 1 or 12
    prev_year = year - 1 if month == 1 else year
    next_month = month + 1 if month < 12 else 1
    next_year = year + 1 if month == 12 else year

    context = {
        "team": team,
        "pending_requests": pending_requests,
        "nearby_teams": nearby_teams,
        "recent_matches": recent_matches,
        "month_name": cal.month_name[month],
        "year": year, "month": month,
        "month_days": month_days,
        "avail_map": avail_map,
        "today": today,
        "prev_month": prev_month, "prev_year": prev_year,
        "next_month": next_month, "next_year": next_year,
        "unread_notifications": team.notifications.filter(user__isnull=True).exclude(read_by=request.user).count(),
    }
    return render(request, "core/dashboard.html", context)


@login_required
def set_availability(request):
    team = get_active_team(request)
    if request.method == "POST":
        d = request.POST.get("date")
        status = request.POST.get("status")
        if d and status:
            Availability.objects.update_or_create(team=team, date=d, defaults={"status": status})
    return redirect(request.META.get("HTTP_REFERER", "core:dashboard"))


@login_required
def find_teams(request):
    team = get_active_team(request)
    form = TeamSearchForm(request.GET or None)
    qs = Team.objects.exclude(id=team.id) if team else Team.objects.all()

    if form.is_valid():
        q = form.cleaned_data.get("q")
        level = form.cleaned_data.get("level")
        playstyle = form.cleaned_data.get("playstyle")
        city = form.cleaned_data.get("city")
        if q:
            qs = qs.filter(Q(name__icontains=q) | Q(home_ground__icontains=q))
        if level:
            qs = qs.filter(level=level)
        if playstyle:
            qs = qs.filter(playstyle=playstyle)
        if city:
            qs = qs.filter(city__icontains=city)

    return render(request, "core/find_teams.html", {"teams": qs, "form": form, "team": team})


@login_required
def find_players(request):
    """Browse/search individual players, regardless of whether they're on a team."""
    form = PlayerSearchForm(request.GET or None)
    qs = User.objects.exclude(pk=request.user.pk).order_by("first_name", "username")

    if form.is_valid():
        q = form.cleaned_data.get("q")
        position = form.cleaned_data.get("position")
        city = form.cleaned_data.get("city")
        if q:
            qs = qs.filter(Q(first_name__icontains=q) | Q(last_name__icontains=q) | Q(username__icontains=q))
        if position:
            qs = qs.filter(position=position)
        if city:
            qs = qs.filter(city__icontains=city)

    qs = list(qs[:60])
    teams_by_player = {}
    for tm in TeamMembership.objects.filter(user__in=qs).select_related("team"):
        teams_by_player.setdefault(tm.user_id, []).append(tm.team)

    players = [{"player": p, "teams": teams_by_player.get(p.id, [])} for p in qs]
    return render(request, "core/find_players.html", {"players": players, "form": form})


@login_required
def remove_player(request, team_pk, player_pk):
    team = get_object_or_404(Team, pk=team_pk)
    membership = get_my_membership(request.user, team)
    if not membership or membership.role != "captain":
        flash.error(request, "Only the captain can remove players.")
        return redirect("core:team_profile", pk=team.pk)

    target = TeamMembership.objects.filter(team=team, user_id=player_pk).select_related("user").first()
    if not target:
        flash.error(request, "That player isn't on this roster.")
        return redirect("core:team_profile", pk=team.pk)
    if target.user_id == request.user.id:
        flash.error(request, "You can't remove yourself as captain. Transfer captaincy first, or delete the team instead.")
        return redirect("core:team_profile", pk=team.pk)

    player_name = target.user.get_full_name() or target.user.username
    target.delete()
    Notification.objects.create(
        user_id=player_pk,
        text=f"You were removed from {team.name}.",
    )
    flash.success(request, f"{player_name} has been removed from the team.")
    return redirect("core:team_profile", pk=team.pk)


@login_required
def team_profile(request, pk):
    profile_team = get_object_or_404(Team, pk=pk)
    my_team = get_active_team(request)
    my_membership = get_my_membership(request.user, profile_team)
    raw_matches = Match.objects.filter(
        Q(home_team=profile_team) | Q(away_team=profile_team), status="completed"
    ).select_related("home_team", "away_team").order_by("-date")[:5]
    recent_matches = [
        {
            "opponent": m.opponent_for(profile_team),
            "date": m.date,
            "score": m.score_for(profile_team),
            "result": m.result_for(profile_team),
            "id": m.id,
        }
        for m in raw_matches
    ]
    roster = TeamMembership.objects.filter(team=profile_team).select_related("user").order_by("role", "user__first_name")
    is_member = bool(my_membership)
    is_captain = bool(my_membership and my_membership.role == "captain")

    available_players = []
    if is_captain:
        # Anyone not already on THIS roster - including players already on
        # other teams, since a player can now belong to more than one team.
        available_players = User.objects.exclude(team_memberships__team=profile_team).exclude(pk=request.user.pk).order_by("first_name", "username")[:20]

    has_pending_request = TeamJoinRequest.objects.filter(
        player=request.user, team=profile_team, status="pending", initiated_by_team=False
    ).exists()

    return render(request, "core/team_profile.html", {
        "profile_team": profile_team, "team": my_team, "recent_matches": recent_matches,
        "is_own": is_member,
        "is_member": is_member,
        "roster": roster,
        "has_pending_request": has_pending_request,
        "is_captain": is_captain,
        "available_players": available_players,
    })


@login_required
def my_team(request):
    team = get_active_team(request)
    if not team:
        return redirect("core:onboard_team")
    membership = get_my_membership(request.user, team)
    is_captain = bool(membership and membership.role == "captain")

    if request.method == "POST":
        if not is_captain:
            flash.error(request, "Only the team captain can edit the team profile.")
            return redirect("core:my_team")
        form = TeamForm(request.POST, request.FILES, instance=team)
        if form.is_valid():
            form.save()
            flash.success(request, "Team profile updated.")
            return redirect("core:my_team")
    else:
        form = TeamForm(instance=team)
    pending_join_requests = team.join_requests.filter(status="pending", initiated_by_team=False).count() if is_captain else 0
    my_teams = get_user_teams(request.user)
    return render(request, "core/my_team.html", {
        "team": team, "form": form, "is_captain": is_captain,
        "pending_join_requests": pending_join_requests,
        "my_teams": my_teams,
    })


@login_required
def send_match_request(request, pk):
    to_team = get_object_or_404(Team, pk=pk)
    from_team = get_active_team(request)
    if not from_team:
        return redirect("core:onboard_team")
    if request.method == "POST":
        form = MatchRequestForm(request.POST)
        if form.is_valid():
            mr = form.save(commit=False)
            mr.from_team = from_team
            mr.to_team = to_team
            mr.save()
            Notification.objects.create(team=to_team, text=f"{from_team.name} sent you a match request.", link=f"/requests/")
            flash.success(request, f"Match request sent to {to_team.name}.")
            return redirect("core:team_profile", pk=to_team.pk)
    else:
        form = MatchRequestForm()
    return render(request, "core/send_request.html", {"form": form, "to_team": to_team})


@login_required
def create_open_request(request):
    team = get_active_team(request)
    if not team:
        return redirect("core:onboard_team")
    if request.method == "POST":
        form = OpenMatchRequestForm(request.POST)
        if form.is_valid():
            mr = form.save(commit=False)
            mr.from_team = team
            mr.to_team = team  # open/public request, no specific opponent yet
            mr.save()
            flash.success(request, "Your open match request has been posted.")
            return redirect("core:match_requests")
    else:
        form = OpenMatchRequestForm()
    return render(request, "core/create_open_request.html", {"form": form})


@login_required
def match_requests(request):
    team = get_active_team(request)
    if not team:
        return redirect("core:onboard_team")
    incoming = MatchRequest.objects.filter(to_team=team, status="pending").exclude(from_team=team).select_related("from_team").order_by("proposed_date")
    sent = MatchRequest.objects.filter(from_team=team).exclude(to_team=team).select_related("to_team").order_by("-created_at")
    open_requests = MatchRequest.objects.filter(from_team=team, to_team=team).order_by("-created_at")
    return render(request, "core/match_requests.html", {
        "team": team, "incoming": incoming, "sent": sent, "open_requests": open_requests,
    })


@login_required
def respond_request(request, pk, action):
    team = get_active_team(request)
    mr = get_object_or_404(MatchRequest, pk=pk, to_team=team)
    if mr.status != "pending":
        flash.error(request, "This request has already been resolved.")
        return redirect("core:dashboard")
    if action == "accept":
        mr.status = "accepted"
        mr.save()
        Match.objects.create(
            home_team=mr.to_team, away_team=mr.from_team, date=mr.proposed_date,
            time=mr.proposed_time, venue=mr.venue, status="scheduled", source_request=mr,
        )
        Notification.objects.create(team=mr.from_team, text=f"{mr.to_team.name} accepted your match request!")
        flash.success(request, f"Match confirmed with {mr.from_team.name}.")
    elif action == "decline":
        mr.status = "declined"
        mr.save()
        Notification.objects.create(team=mr.from_team, text=f"{mr.to_team.name} declined your match request.")
        flash.info(request, "Request declined.")
    return redirect("core:dashboard")


@login_required
def cancel_match_request(request, pk):
    """Withdraw a match request you sent, before the other team has responded."""
    team = get_active_team(request)
    mr = get_object_or_404(MatchRequest, pk=pk, from_team=team)
    if mr.status != "pending":
        flash.error(request, "Only pending requests can be cancelled.")
        return redirect("core:match_requests")
    mr.status = "cancelled"
    mr.save()
    if mr.to_team_id != mr.from_team_id:
        Notification.objects.create(team=mr.to_team, text=f"{team.name} cancelled their match request.")
    flash.info(request, "Match request cancelled.")
    return redirect("core:match_requests")


@login_required
def inbox(request):
    team = get_active_team(request)
    convo_list = build_convo_list(request, team)
    return render(request, "core/inbox.html", {"team": team, "convo_list": convo_list})


@login_required
def conversation_view(request, pk):
    team = get_active_team(request)
    convo = get_object_or_404(Conversation, pk=pk)
    if not team or team.id not in (convo.team_a_id, convo.team_b_id):
        flash.error(request, "You don't have access to this conversation.")
        return redirect("core:inbox")
    other = convo.other(team)
    if request.method == "POST":
        form = MessageForm(request.POST)
        if form.is_valid():
            msg = form.save(commit=False)
            msg.conversation = convo
            msg.sender = team
            msg.save()
            return redirect("core:conversation", pk=convo.pk)
    else:
        form = MessageForm()
    for m in convo.messages.exclude(sender=team):
        m.read_by.add(request.user)
    conversations = build_convo_list(request, team)
    return render(request, "core/conversation.html", {
        "team": team, "convo": convo, "other": other, "msgs": convo.messages.all(), "form": form,
        "conversations": conversations, "active_kind": "team", "active_pk": convo.pk,
    })


@login_required
def start_conversation(request, pk):
    team = get_active_team(request)
    if not team:
        return redirect("core:onboard_team")
    other = get_object_or_404(Team, pk=pk)
    convo = Conversation.between(team, other)
    return redirect("core:conversation", pk=convo.pk)


@login_required
def player_conversation_view(request, pk):
    convo = get_object_or_404(PlayerConversation, pk=pk)
    if request.user.id not in (convo.player_a_id, convo.player_b_id):
        flash.error(request, "You don't have access to this conversation.")
        return redirect("core:inbox")
    other = convo.other(request.user)
    if request.method == "POST":
        form = PlayerMessageForm(request.POST)
        if form.is_valid():
            msg = form.save(commit=False)
            msg.conversation = convo
            msg.sender = request.user
            msg.save()
            return redirect("core:player_conversation", pk=convo.pk)
    else:
        form = PlayerMessageForm()
    convo.dm_messages.exclude(sender=request.user).update(read=True)
    team = get_active_team(request)
    conversations = build_convo_list(request, team)
    return render(request, "core/player_conversation.html", {
        "team": team, "convo": convo, "other": other, "msgs": convo.dm_messages.all(), "form": form,
        "conversations": conversations, "active_kind": "player", "active_pk": convo.pk,
    })


@login_required
def start_player_conversation(request, pk):
    other = get_object_or_404(User, pk=pk)
    if other.id == request.user.id:
        flash.error(request, "You can't message yourself.")
        return redirect("accounts:player_profile", pk=request.user.pk)
    convo = PlayerConversation.between(request.user, other)
    return redirect("core:player_conversation", pk=convo.pk)


@login_required
def notifications_view(request):
    team_ids = list(TeamMembership.objects.filter(user=request.user).values_list("team_id", flat=True))
    q = Q(user=request.user)
    if team_ids:
        q |= Q(team_id__in=team_ids)
    notes = list(Notification.objects.filter(q)[:30])

    personal_ids = [n.id for n in notes if n.user_id]
    if personal_ids:
        Notification.objects.filter(id__in=personal_ids, is_read=False).update(is_read=True)

    team_notes = [n for n in notes if n.team_id and not n.user_id]
    for n in team_notes:
        n.read_by.add(request.user)

    # Actionable items surfaced directly on this page, so a player doesn't
    # have to go hunting for the team-invite/join-request screens:
    # - a team invited this player -> player accepts/declines here
    # - a player asked to join a team this user captains -> captain accepts/declines here
    pending_invites = TeamJoinRequest.objects.filter(
        player=request.user, status="pending", initiated_by_team=True
    ).select_related("team")

    captain_team_ids = list(
        TeamMembership.objects.filter(user=request.user, role="captain").values_list("team_id", flat=True)
    )
    pending_join_requests = TeamJoinRequest.objects.filter(
        team_id__in=captain_team_ids, status="pending", initiated_by_team=False
    ).select_related("team", "player") if captain_team_ids else TeamJoinRequest.objects.none()

    return render(request, "core/notifications.html", {
        "team": get_active_team(request),
        "notes": notes,
        "pending_invites": pending_invites,
        "pending_join_requests": pending_join_requests,
    })


# ---------------------------------------------------------------------
# Join requests - a player without a team asking to join one's roster
# ---------------------------------------------------------------------


@login_required
def send_join_request(request, pk):
    team = get_object_or_404(Team, pk=pk)
    if TeamMembership.objects.filter(user=request.user, team=team).exists():
        flash.error(request, "You're already on this team.")
        return redirect("core:team_profile", pk=team.pk)
    if TeamJoinRequest.objects.filter(player=request.user, team=team, status="pending", initiated_by_team=False).exists():
        flash.info(request, "You already have a pending request to this team.")
        return redirect("core:team_profile", pk=team.pk)

    if request.method == "POST":
        form = TeamJoinRequestForm(request.POST)
        if form.is_valid():
            jr = form.save(commit=False)
            jr.player = request.user
            jr.team = team
            jr.initiated_by_team = False
            jr.save()
            Notification.objects.create(
                team=team,
                text=f"{request.user.get_full_name() or request.user.username} requested to join your team.",
                link="/join-requests/",
            )
            flash.success(request, f"Request sent to {team.name}.")
            return redirect("core:team_profile", pk=team.pk)
    else:
        form = TeamJoinRequestForm()
    return render(request, "core/send_join_request.html", {"form": form, "team": team})


@login_required
def invite_player(request, team_pk, player_pk):
    team = get_object_or_404(Team, pk=team_pk)
    player = get_object_or_404(User, pk=player_pk)
    membership = get_my_membership(request.user, team)
    if not membership or membership.role != "captain":
        flash.error(request, "Only the captain can invite players.")
        return redirect("core:team_profile", pk=team.pk)

    if TeamMembership.objects.filter(user=player, team=team).exists():
        flash.error(request, f"{player} is already on this team.")
        return redirect("core:team_profile", pk=team.pk)

    if TeamJoinRequest.objects.filter(player=player, team=team, status="pending", initiated_by_team=True).exists():
        flash.info(request, f"An invite is already pending for {player}.")
        return redirect("core:team_profile", pk=team.pk)

    TeamJoinRequest.objects.create(
        player=player,
        team=team,
        message="",
        initiated_by_team=True,
        status="pending",
    )
    Notification.objects.create(
        user=player,
        text=f"{team.name} invited you to join their team.",
        link=team.get_absolute_url(),
    )
    flash.success(request, f"Invite sent to {player}.")
    return redirect("core:team_profile", pk=team.pk)


@login_required
def team_join_requests(request):
    team = get_active_team(request)
    if not team:
        return redirect("core:onboard_team")
    membership = get_my_membership(request.user, team)
    is_captain = bool(membership and membership.role == "captain")
    incoming = team.join_requests.filter(status="pending", initiated_by_team=False).select_related("player") if is_captain else []
    history = team.join_requests.select_related("player")[:10] if is_captain else []
    return render(request, "core/join_requests.html", {
        "team": team, "incoming": incoming, "history": history, "is_captain": is_captain,
    })


@login_required
def respond_join_request(request, pk, action):
    jr = get_object_or_404(TeamJoinRequest, pk=pk)
    team = jr.team
    membership = get_my_membership(request.user, team)
    if not membership or membership.role != "captain":
        flash.error(request, "Only the captain can respond to join requests.")
        return redirect("core:team_join_requests")

    if action == "accept":
        if TeamMembership.objects.filter(user=jr.player, team=team).exists():
            flash.error(request, f"{jr.player} is already on this team.")
        else:
            TeamMembership.objects.create(team=team, user=jr.player, role="player")
            jr.status = "accepted"
            jr.save()
            Notification.objects.create(user=jr.player, text=f"You joined {team.name}!", link=f"/my-team/")
            flash.success(request, f"{jr.player} added to the squad.")
    elif action == "decline":
        jr.status = "declined"
        jr.save()
        Notification.objects.create(user=jr.player, text=f"{team.name} declined your request to join.")
        flash.info(request, "Request declined.")
    referer = request.META.get("HTTP_REFERER")
    if referer:
        return redirect(referer)
    return redirect("core:team_join_requests")


# ---------------------------------------------------------------------
# Matches - scheduled/completed matches, and recording result/scorers/
# ratings once a match has ended
# ---------------------------------------------------------------------


@login_required
def matches_list(request):
    team = get_active_team(request)
    if not team:
        return redirect("core:onboard_team")
    base = Q(home_team=team) | Q(away_team=team)
    upcoming_qs = Match.objects.filter(base, status="scheduled").select_related("home_team", "away_team").order_by("date", "time")
    completed_qs = Match.objects.filter(base, status="completed").select_related("home_team", "away_team").order_by("-date")[:20]
    cancelled_qs = Match.objects.filter(base, status="cancelled").select_related("home_team", "away_team").order_by("-date")[:10]

    upcoming = [
        {
            "id": m.id, "opponent": m.opponent_for(team), "date": m.date, "time": m.time, "venue": m.venue,
            "cancel_pending": bool(m.cancel_requested_by_id),
        }
        for m in upcoming_qs
    ]
    completed = [
        {"id": m.id, "opponent": m.opponent_for(team), "date": m.date, "score": m.score_for(team), "result": m.result_for(team)}
        for m in completed_qs
    ]
    cancelled = [
        {"id": m.id, "opponent": m.opponent_for(team), "date": m.date, "venue": m.venue}
        for m in cancelled_qs
    ]
    return render(request, "core/matches.html", {"team": team, "upcoming": upcoming, "completed": completed, "cancelled": cancelled})


@login_required
def match_detail(request, pk):
    match = get_object_or_404(Match.objects.select_related("home_team", "away_team", "cancel_requested_by"), pk=pk)
    team = get_active_team(request)
    if not team or team.id not in (match.home_team_id, match.away_team_id):
        flash.error(request, "You don't have access to this match.")
        return redirect("core:dashboard")

    membership = get_my_membership(request.user, team)
    is_captain = bool(membership and membership.role == "captain")

    roster = TeamMembership.objects.filter(
        team__in=[match.home_team, match.away_team]
    ).select_related("user", "team").order_by("team_id", "user__first_name")

    goals_map = {g.scorer_id: g.goals for g in match.goals.all()}
    ratings_map = {r.player_id: r.rating for r in match.ratings.all()}

    home_roster = [m for m in roster if m.team_id == match.home_team_id]
    away_roster = [m for m in roster if m.team_id == match.away_team_id]
    top_scorers = match.goals.select_related("scorer", "team").order_by("-goals")

    return render(request, "core/match_detail.html", {
        "team": team, "match": match, "is_captain": is_captain,
        "home_roster": home_roster, "away_roster": away_roster,
        "goals_map": goals_map, "ratings_map": ratings_map,
        "top_scorers": top_scorers, "rating_range": range(1, 11),
        "opponent": match.opponent_for(team),
        "cancel_requested_by_me": bool(match.cancel_requested_by_id and match.cancel_requested_by_id == team.id),
        "cancel_requested_by_them": bool(match.cancel_requested_by_id and match.cancel_requested_by_id != team.id),
    })


@login_required
def submit_match_result(request, pk):
    match = get_object_or_404(Match, pk=pk)
    team = get_active_team(request)
    if not team or team.id not in (match.home_team_id, match.away_team_id):
        flash.error(request, "You don't have access to this match.")
        return redirect("core:dashboard")

    membership = get_my_membership(request.user, team)
    if not membership or membership.role != "captain":
        flash.error(request, "Only team captains can submit the match result.")
        return redirect("core:match_detail", pk=match.pk)

    if request.method != "POST":
        return redirect("core:match_detail", pk=match.pk)

    home_score = request.POST.get("home_score", "").strip()
    away_score = request.POST.get("away_score", "").strip()
    if home_score == "" or away_score == "":
        flash.error(request, "Enter both team scores.")
        return redirect("core:match_detail", pk=match.pk)

    match.home_score = int(home_score)
    match.away_score = int(away_score)
    match.status = "completed"
    match.cancel_requested_by = None
    match.save()

    roster = TeamMembership.objects.filter(team__in=[match.home_team, match.away_team]).select_related("user")
    for m in roster:
        goals_raw = request.POST.get(f"goals_{m.user_id}", "").strip()
        rating_raw = request.POST.get(f"rating_{m.user_id}", "").strip()

        try:
            goals_val = int(goals_raw) if goals_raw else 0
        except ValueError:
            goals_val = 0
        if goals_val > 0:
            MatchGoal.objects.update_or_create(
                match=match, scorer=m.user, defaults={"team": m.team, "goals": goals_val}
            )
        else:
            MatchGoal.objects.filter(match=match, scorer=m.user).delete()

        if rating_raw:
            try:
                rating_val = max(1, min(10, int(rating_raw)))
                PlayerRating.objects.update_or_create(
                    match=match, player=m.user, defaults={"team": m.team, "rating": rating_val}
                )
            except ValueError:
                pass

    other_team = match.away_team if team.id == match.home_team_id else match.home_team
    Notification.objects.create(
        team=other_team,
        text=f"{team.name} submitted the result for your match: {match.score_for(other_team)}.",
        link=f"/matches/{match.pk}/",
    )
    flash.success(request, "Match result, scorers and ratings saved.")
    return redirect("core:match_detail", pk=match.pk)


@login_required
def request_cancel_match(request, pk):
    """A captain asks to call off a scheduled match - the other captain must agree before it's actually cancelled."""
    match = get_object_or_404(Match, pk=pk)
    team = get_active_team(request)
    if not team or team.id not in (match.home_team_id, match.away_team_id):
        flash.error(request, "You don't have access to this match.")
        return redirect("core:dashboard")

    membership = get_my_membership(request.user, team)
    if not membership or membership.role != "captain":
        flash.error(request, "Only team captains can request a match cancellation.")
        return redirect("core:match_detail", pk=match.pk)

    if match.status != "scheduled":
        flash.error(request, "Only scheduled matches can be cancelled.")
        return redirect("core:match_detail", pk=match.pk)

    if match.cancel_requested_by_id:
        flash.info(request, "A cancellation request is already pending for this match.")
        return redirect("core:match_detail", pk=match.pk)

    match.cancel_requested_by = team
    match.save()
    other_team = match.opponent_for(team)
    Notification.objects.create(
        team=other_team,
        text=f"{team.name} requested to cancel your match on {match.date}.",
        link=f"/matches/{match.pk}/",
    )
    flash.success(request, "Cancellation request sent. The match will be cancelled once the other team agrees.")
    return redirect("core:match_detail", pk=match.pk)


@login_required
def respond_cancel_match(request, pk, action):
    """The other captain accepts/declines a pending cancellation request, or the original requester withdraws it."""
    match = get_object_or_404(Match, pk=pk)
    team = get_active_team(request)
    if not team or team.id not in (match.home_team_id, match.away_team_id):
        flash.error(request, "You don't have access to this match.")
        return redirect("core:dashboard")

    membership = get_my_membership(request.user, team)
    if not membership or membership.role != "captain":
        flash.error(request, "Only team captains can respond to a cancellation request.")
        return redirect("core:match_detail", pk=match.pk)

    if not match.cancel_requested_by_id:
        flash.error(request, "There's no pending cancellation request for this match.")
        return redirect("core:match_detail", pk=match.pk)

    requester = match.cancel_requested_by
    other_team = match.opponent_for(requester)

    if action == "withdraw":
        if requester.id != team.id:
            flash.error(request, "Only the team that requested cancellation can withdraw it.")
            return redirect("core:match_detail", pk=match.pk)
        match.cancel_requested_by = None
        match.save()
        Notification.objects.create(team=other_team, text=f"{team.name} withdrew their request to cancel your match.", link=f"/matches/{match.pk}/")
        flash.info(request, "Cancellation request withdrawn.")
    elif action == "accept":
        if requester.id == team.id:
            flash.error(request, "Waiting for the other team to respond.")
            return redirect("core:match_detail", pk=match.pk)
        match.status = "cancelled"
        match.cancel_requested_by = None
        match.save()
        Notification.objects.create(team=requester, text=f"{team.name} agreed to cancel your match on {match.date}.", link=f"/matches/{match.pk}/")
        flash.success(request, "Match cancelled by mutual agreement.")
    elif action == "decline":
        if requester.id == team.id:
            flash.error(request, "Waiting for the other team to respond.")
            return redirect("core:match_detail", pk=match.pk)
        match.cancel_requested_by = None
        match.save()
        Notification.objects.create(team=requester, text=f"{team.name} declined to cancel your match on {match.date}.", link=f"/matches/{match.pk}/")
        flash.info(request, "Cancellation request declined. The match stays scheduled.")
    else:
        flash.error(request, "Unknown action.")
    return redirect("core:match_detail", pk=match.pk)