import calendar as cal

from django.contrib import messages as flash
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import (AvailabilityForm, MatchRequestForm, MessageForm,
                     OpenMatchRequestForm, TeamForm, TeamJoinRequestForm,
                     TeamSearchForm)
from .models import (Availability, Conversation, Match, MatchGoal,
                      MatchRequest, Notification, PlayerRating, Team,
                      TeamJoinRequest, TeamMembership)

User = get_user_model()


def get_my_team(user):
    membership = TeamMembership.objects.filter(user=user).select_related("team").first()
    return membership.team if membership else None


def get_my_membership(user, team):
    if not team:
        return None
    return TeamMembership.objects.filter(user=user, team=team).first()


@login_required
def onboard_team(request):
    if get_my_team(request.user):
        return redirect("core:dashboard")
    if request.method == "POST":
        form = TeamForm(request.POST, request.FILES)
        if form.is_valid():
            team = form.save(commit=False)
            team.captain = request.user
            team.save()
            TeamMembership.objects.create(team=team, user=request.user, role="captain")
            flash.success(request, "Team profile created!")
            return redirect("core:dashboard")
    else:
        form = TeamForm()
    return render(request, "core/onboard_team.html", {"form": form})


@login_required
def dashboard(request):
    team = get_my_team(request.user)
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
        "unread_notifications": team.notifications.filter(is_read=False).count(),
    }
    return render(request, "core/dashboard.html", context)


@login_required
def set_availability(request):
    team = get_my_team(request.user)
    if request.method == "POST":
        d = request.POST.get("date")
        status = request.POST.get("status")
        if d and status:
            Availability.objects.update_or_create(team=team, date=d, defaults={"status": status})
    return redirect(request.META.get("HTTP_REFERER", "core:dashboard"))


@login_required
def find_teams(request):
    team = get_my_team(request.user)
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
def team_profile(request, pk):
    profile_team = get_object_or_404(Team, pk=pk)
    my_team = get_my_team(request.user)
    my_membership = get_my_membership(request.user, my_team)
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
    available_players = []
    is_captain = bool(my_membership and my_membership.role == "captain" and my_team and my_team.id == profile_team.id)
    if is_captain:
        available_players = User.objects.filter(team_memberships__isnull=True).exclude(pk=request.user.pk).order_by("first_name", "username")[:20]

    has_pending_request = False
    if not my_team:
        has_pending_request = TeamJoinRequest.objects.filter(
            player=request.user, team=profile_team, status="pending"
        ).exists()

    return render(request, "core/team_profile.html", {
        "profile_team": profile_team, "team": my_team, "recent_matches": recent_matches,
        "is_own": my_team and my_team.id == profile_team.id,
        "roster": roster,
        "has_pending_request": has_pending_request,
        "is_captain": is_captain,
        "available_players": available_players,
    })


@login_required
def my_team(request):
    team = get_my_team(request.user)
    if not team:
        return redirect("core:onboard_team")
    if request.method == "POST":
        form = TeamForm(request.POST, request.FILES, instance=team)
        if form.is_valid():
            form.save()
            flash.success(request, "Team profile updated.")
            return redirect("core:my_team")
    else:
        form = TeamForm(instance=team)
    membership = get_my_membership(request.user, team)
    is_captain = bool(membership and membership.role == "captain")
    pending_join_requests = team.join_requests.filter(status="pending").count() if is_captain else 0
    return render(request, "core/my_team.html", {
        "team": team, "form": form, "is_captain": is_captain,
        "pending_join_requests": pending_join_requests,
    })


@login_required
def send_match_request(request, pk):
    to_team = get_object_or_404(Team, pk=pk)
    from_team = get_my_team(request.user)
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
    team = get_my_team(request.user)
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
    team = get_my_team(request.user)
    incoming = MatchRequest.objects.filter(to_team=team, status="pending").exclude(from_team=team).select_related("from_team").order_by("proposed_date")
    sent = MatchRequest.objects.filter(from_team=team).exclude(to_team=team).select_related("to_team").order_by("-created_at")
    open_requests = MatchRequest.objects.filter(from_team=team, to_team=team).order_by("-created_at")
    return render(request, "core/match_requests.html", {
        "team": team, "incoming": incoming, "sent": sent, "open_requests": open_requests,
    })


@login_required
def respond_request(request, pk, action):
    team = get_my_team(request.user)
    mr = get_object_or_404(MatchRequest, pk=pk, to_team=team)
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
def inbox(request):
    team = get_my_team(request.user)
    if not team:
        return redirect("core:onboard_team")
    conversations = Conversation.objects.filter(Q(team_a=team) | Q(team_b=team)).order_by("-created_at")
    convo_list = []
    for c in conversations:
        last = c.last_message()
        convo_list.append({"conversation": c, "other": c.other(team), "last": last})
    convo_list.sort(key=lambda x: x["last"].sent_at if x["last"] else timezone.now(), reverse=True)
    return render(request, "core/inbox.html", {"team": team, "convo_list": convo_list})


@login_required
def conversation_view(request, pk):
    team = get_my_team(request.user)
    convo = get_object_or_404(Conversation, pk=pk)
    if team.id not in (convo.team_a_id, convo.team_b_id):
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
    convo.messages.exclude(sender=team).update(read=True)
    conversations_qs = Conversation.objects.filter(Q(team_a=team) | Q(team_b=team))
    conversations = [{"pk": c.pk, "other": c.other(team)} for c in conversations_qs]
    return render(request, "core/conversation.html", {
        "team": team, "convo": convo, "other": other, "msgs": convo.messages.all(), "form": form,
        "conversations": conversations,
    })


@login_required
def start_conversation(request, pk):
    team = get_my_team(request.user)
    other = get_object_or_404(Team, pk=pk)
    convo = Conversation.between(team, other)
    return redirect("core:conversation", pk=convo.pk)


@login_required
def notifications_view(request):
    team = get_my_team(request.user)
    q = Q(user=request.user)
    if team:
        q |= Q(team=team)
    notes = Notification.objects.filter(q)[:30]
    Notification.objects.filter(q, is_read=False).update(is_read=True)
    return render(request, "core/notifications.html", {"team": team, "notes": notes})


# ---------------------------------------------------------------------
# Join requests - a player without a team asking to join one's roster
# ---------------------------------------------------------------------


@login_required
def send_join_request(request, pk):
    team = get_object_or_404(Team, pk=pk)
    if get_my_team(request.user):
        flash.error(request, "You're already on a team.")
        return redirect("core:team_profile", pk=team.pk)
    if TeamJoinRequest.objects.filter(player=request.user, team=team, status="pending").exists():
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

    if TeamMembership.objects.filter(user=player).exists():
        flash.error(request, f"{player} is already on a team.")
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
    team = get_my_team(request.user)
    if not team:
        return redirect("core:onboard_team")
    membership = get_my_membership(request.user, team)
    is_captain = bool(membership and membership.role == "captain")
    incoming = team.join_requests.filter(status="pending", initiated_by_team=False).select_related("player") if is_captain else []
    history = team.join_requests.exclude(status="pending").select_related("player")[:10] if is_captain else []
    return render(request, "core/join_requests.html", {
        "team": team, "incoming": incoming, "history": history, "is_captain": is_captain,
    })


@login_required
def respond_join_request(request, pk, action):
    team = get_my_team(request.user)
    jr = get_object_or_404(TeamJoinRequest, pk=pk, team=team)
    membership = get_my_membership(request.user, team)
    if not membership or membership.role != "captain":
        flash.error(request, "Only the captain can respond to join requests.")
        return redirect("core:team_join_requests")

    if action == "accept":
        if get_my_team(jr.player):
            flash.error(request, f"{jr.player} has already joined another team.")
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
    return redirect("core:team_join_requests")


# ---------------------------------------------------------------------
# Matches - scheduled/completed matches, and recording result/scorers/
# ratings once a match has ended
# ---------------------------------------------------------------------


@login_required
def matches_list(request):
    team = get_my_team(request.user)
    if not team:
        return redirect("core:onboard_team")
    base = Q(home_team=team) | Q(away_team=team)
    upcoming_qs = Match.objects.filter(base, status="scheduled").select_related("home_team", "away_team").order_by("date", "time")
    completed_qs = Match.objects.filter(base, status="completed").select_related("home_team", "away_team").order_by("-date")[:20]

    upcoming = [
        {"id": m.id, "opponent": m.opponent_for(team), "date": m.date, "time": m.time, "venue": m.venue}
        for m in upcoming_qs
    ]
    completed = [
        {"id": m.id, "opponent": m.opponent_for(team), "date": m.date, "score": m.score_for(team), "result": m.result_for(team)}
        for m in completed_qs
    ]
    return render(request, "core/matches.html", {"team": team, "upcoming": upcoming, "completed": completed})


@login_required
def match_detail(request, pk):
    match = get_object_or_404(Match.objects.select_related("home_team", "away_team"), pk=pk)
    team = get_my_team(request.user)
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
    })


@login_required
def submit_match_result(request, pk):
    match = get_object_or_404(Match, pk=pk)
    team = get_my_team(request.user)
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