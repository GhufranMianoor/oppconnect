import calendar as cal
from datetime import date

from django.contrib import messages as flash
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone

from .forms import (AvailabilityForm, MatchRequestForm, MessageForm,
                     OpenMatchRequestForm, TeamForm, TeamSearchForm)
from .models import (Availability, Conversation, Match, MatchRequest,
                      Notification, Team, TeamMembership)


def get_my_team(user):
    membership = TeamMembership.objects.filter(user=user).select_related("team").first()
    return membership.team if membership else None


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

    raw_matches = Match.objects.filter(Q(home_team=team) | Q(away_team=team), status="completed").order_by("-date")[:5]
    recent_matches = [
        {
            "opponent": m.opponent_for(team),
            "date": m.date,
            "score": m.score_for(team),
            "result": m.result_for(team),
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
    raw_matches = Match.objects.filter(
        Q(home_team=profile_team) | Q(away_team=profile_team), status="completed"
    ).order_by("-date")[:5]
    recent_matches = [
        {
            "opponent": m.opponent_for(profile_team),
            "date": m.date,
            "score": m.score_for(profile_team),
            "result": m.result_for(profile_team),
        }
        for m in raw_matches
    ]
    return render(request, "core/team_profile.html", {
        "profile_team": profile_team, "team": my_team, "recent_matches": recent_matches,
        "is_own": my_team and my_team.id == profile_team.id,
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
    return render(request, "core/my_team.html", {"team": team, "form": form})


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
    open_requests = MatchRequest.objects.filter(from_team=team, to_team__isnull=True).order_by("-created_at")
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
    notes = team.notifications.all()[:30]
    team.notifications.filter(is_read=False).update(is_read=True)
    return render(request, "core/notifications.html", {"team": team, "notes": notes})
