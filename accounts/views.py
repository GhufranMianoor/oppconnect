from django.contrib import messages as flash
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from .forms import ProfileForm, SignUpForm
from .models import User


def signup(request):
    if request.method == "POST":
        form = SignUpForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            return redirect("core:onboard_team")
    else:
        form = SignUpForm()
    return render(request, "accounts/signup.html", {"form": form})


def logout_view(request):
    """
    Plain function-based logout that works on a simple GET link.
    Django's built-in LogoutView requires POST, which can be tripped up by
    SECURE_SSL_REDIRECT converting a POST into a GET on some proxy setups
    (301 redirects turn POST into GET in the browser). A GET-based logout
    sidesteps that class of bug entirely - logging a user out has no
    destructive side effect worth CSRF-protecting against.
    """
    logout(request)
    return redirect("accounts:login")


@login_required
def player_profile(request, pk):
    from core.models import TeamJoinRequest, TeamMembership

    player = get_object_or_404(User, pk=pk)
    membership = TeamMembership.objects.filter(user=player).select_related("team").first()
    pending_invitations = []
    if player.id == request.user.id:
        pending_invitations = TeamJoinRequest.objects.filter(
            player=player,
            status="pending",
            initiated_by_team=True,
        ).select_related("team")
    return render(request, "accounts/player_profile.html", {
        "player": player,
        "membership": membership,
        "is_own": player.id == request.user.id,
        "pending_invitations": pending_invitations,
    })


@login_required
def edit_profile(request):
    if request.method == "POST":
        form = ProfileForm(request.POST, request.FILES, instance=request.user)
        if form.is_valid():
            form.save()
            flash.success(request, "Profile updated.")
            return redirect("accounts:player_profile", pk=request.user.pk)
    else:
        form = ProfileForm(instance=request.user)
    return render(request, "accounts/edit_profile.html", {"form": form})


@login_required
def respond_team_invite(request, pk, action):
    from core.models import Notification, TeamJoinRequest, TeamMembership

    invite = get_object_or_404(TeamJoinRequest, pk=pk, player=request.user, initiated_by_team=True)
    if action == "accept":
        if TeamMembership.objects.filter(user=request.user).exists():
            flash.error(request, "You're already on a team.")
        else:
            TeamMembership.objects.create(team=invite.team, user=request.user, role="player")
            invite.status = "accepted"
            invite.save()
            Notification.objects.create(team=invite.team, text=f"{request.user.get_full_name() or request.user.username} accepted your invite.")
            flash.success(request, f"You joined {invite.team.name}.")
    elif action == "decline":
        invite.status = "declined"
        invite.save()
        Notification.objects.create(team=invite.team, text=f"{request.user.get_full_name() or request.user.username} declined your invite.")
        flash.info(request, "Invite declined.")
    return redirect("accounts:player_profile", pk=request.user.pk)