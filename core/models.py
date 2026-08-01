from django.conf import settings
from django.db import models
from django.urls import reverse
from django.utils.functional import cached_property

from .fields import EncryptedTextField

User = settings.AUTH_USER_MODEL

LEVEL_CHOICES = [
    ("below average", "Below Average"),
    ("average", "Average"),
    ("good", "Good"),
    ("very good", "Very Good"),
    ("strong", "Strong")
]

PLAYSTYLE_CHOICES = [
    ("possession", "Possession"),
    ("counter_attack", "Counter Attack"),
    ("high_press", "High Press"),
    ("defensive", "Defensive"),
    ("balanced", "Balanced"),
]

AVAILABILITY_CHOICES = [
    ("available", "Available"),
    ("maybe", "Maybe"),
    ("unavailable", "Not Available"),
]


class Team(models.Model):
    name = models.CharField(max_length=120, unique=True)
    logo = models.ImageField(upload_to="team_logos/", blank=True, null=True)
    captain = models.ForeignKey(User, on_delete=models.CASCADE, related_name="captained_teams")
    bio = models.TextField(blank=True)
    home_ground = models.CharField(max_length=150, blank=True)
    city = models.CharField(max_length=100, default="Karachi")
    level = models.CharField(max_length=20, choices=LEVEL_CHOICES, default="below average")
    playstyle = models.CharField(max_length=20, choices=PLAYSTYLE_CHOICES, default="balanced")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse("core:team_profile", args=[self.pk])

    @cached_property
    def _completed_matches(self):
        """
        Fetch every completed match for this team ONE time (one query,
        select_related to avoid extra FK lookups for home_team/away_team),
        cached on the instance so repeated property access below - and
        repeated template access to team.wins, team.losses, etc - doesn't
        re-hit the database each time.
        """
        from itertools import chain
        qs_kwargs = dict(status="completed")
        home = self.home_matches.filter(**qs_kwargs).select_related("home_team", "away_team")
        away = self.away_matches.filter(**qs_kwargs).select_related("home_team", "away_team")
        return list(chain(home, away))

    @cached_property
    def matches_played(self):
        return len(self._completed_matches)

    @cached_property
    def wins(self):
        return sum(1 for m in self._completed_matches if m.winner_id == self.id)

    @cached_property
    def losses(self):
        return sum(1 for m in self._completed_matches if m.winner_id is not None and m.winner_id != self.id)

    @cached_property
    def draws(self):
        return sum(1 for m in self._completed_matches if m.winner_id is None)

    @cached_property
    def win_rate(self):
        played = self.matches_played
        return round((self.wins / played) * 100) if played else 0

    @cached_property
    def goals_scored(self):
        total = 0
        for m in self._completed_matches:
            total += (m.home_score if m.home_team_id == self.id else m.away_score) or 0
        return total

    @cached_property
    def goals_conceded(self):
        total = 0
        for m in self._completed_matches:
            total += (m.away_score if m.home_team_id == self.id else m.home_score) or 0
        return total

    @cached_property
    def clean_sheets(self):
        count = 0
        for m in self._completed_matches:
            conceded = m.away_score if m.home_team_id == self.id else m.home_score
            if (conceded or 0) == 0:
                count += 1
        return count

    @cached_property
    def reliability(self):
        """% of accepted match requests that were completed (not cancelled)."""
        counts = MatchRequest.objects.filter(
            models.Q(from_team=self) | models.Q(to_team=self), status__in=["accepted", "completed"]
        ).aggregate(
            accepted=models.Count("id"),
            completed=models.Count("id", filter=models.Q(status="completed")),
        )
        accepted = counts["accepted"]
        completed = counts["completed"]
        if accepted == 0:
            return 100
        return round((completed / accepted) * 100)


class TeamMembership(models.Model):
    ROLE_CHOICES = [("captain", "Captain"), ("player", "Player")]
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="members")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="team_memberships")
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default="player")
    position = models.CharField(max_length=50, blank=True)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("team", "user")

    def __str__(self):
        return f"{self.user} @ {self.team} ({self.role})"


class Availability(models.Model):
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="availability")
    date = models.DateField()
    status = models.CharField(max_length=15, choices=AVAILABILITY_CHOICES, default="available")

    class Meta:
        unique_together = ("team", "date")
        ordering = ["date"]

    def __str__(self):
        return f"{self.team} - {self.date} - {self.status}"


class MatchRequest(models.Model):
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("accepted", "Accepted"),
        ("declined", "Declined"),
        ("cancelled", "Cancelled"),
        ("completed", "Completed"),
    ]
    from_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="sent_requests")
    to_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="received_requests")
    proposed_date = models.DateField()
    proposed_time = models.TimeField()
    venue = models.CharField(max_length=150)
    message = models.TextField(blank=True)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.from_team} -> {self.to_team} on {self.proposed_date}"


class Match(models.Model):
    STATUS_CHOICES = [("scheduled", "Scheduled"), ("completed", "Completed"), ("cancelled", "Cancelled")]
    home_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="home_matches")
    away_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="away_matches")
    date = models.DateField()
    time = models.TimeField()
    venue = models.CharField(max_length=150)
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default="scheduled")
    home_score = models.PositiveIntegerField(blank=True, null=True)
    away_score = models.PositiveIntegerField(blank=True, null=True)
    source_request = models.OneToOneField(MatchRequest, on_delete=models.SET_NULL, blank=True, null=True, related_name="match")

    class Meta:
        ordering = ["-date", "-time"]

    def __str__(self):
        return f"{self.home_team} vs {self.away_team} - {self.date}"

    @property
    def winner_id(self):
        if self.home_score is None or self.away_score is None:
            return None
        if self.home_score == self.away_score:
            return None
        return self.home_team_id if self.home_score > self.away_score else self.away_team_id

    def result_for(self, team):
        if self.home_score is None or self.away_score is None:
            return None
        if self.home_score == self.away_score:
            return "D"
        winner = self.home_team_id if self.home_score > self.away_score else self.away_team_id
        return "W" if winner == team.id else "L"

    def opponent_for(self, team):
        return self.away_team if self.home_team_id == team.id else self.home_team

    def score_for(self, team):
        if self.home_team_id == team.id:
            return f"{self.home_score} - {self.away_score}"
        return f"{self.away_score} - {self.home_score}"


class Conversation(models.Model):
    team_a = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="conversations_a")
    team_b = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="conversations_b")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("team_a", "team_b")

    def other(self, team):
        return self.team_b if self.team_a_id == team.id else self.team_a

    def last_message(self):
        return self.messages.order_by("-sent_at").first()

    @staticmethod
    def between(team1, team2):
        a, b = sorted([team1, team2], key=lambda t: t.id)
        convo, _ = Conversation.objects.get_or_create(team_a=a, team_b=b)
        return convo


class Message(models.Model):
    conversation = models.ForeignKey(Conversation, on_delete=models.CASCADE, related_name="messages")
    sender = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="sent_messages")
    text = EncryptedTextField()  # encrypted at rest, decrypted transparently on read
    sent_at = models.DateTimeField(auto_now_add=True)
    read = models.BooleanField(default=False)

    class Meta:
        ordering = ["sent_at"]

    def __str__(self):
        return f"{self.sender}: {self.text[:30]}"


class Notification(models.Model):
    # A notification targets a team (visible to all its members) and/or a
    # specific user (e.g. a player who isn't on a team yet, so has no team
    # inbox to land in - like someone whose join request just got a reply).
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="notifications", null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="notifications", null=True, blank=True)
    text = models.CharField(max_length=255)
    link = models.CharField(max_length=255, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]


class TeamJoinRequest(models.Model):
    """A player asking to join an existing team's roster."""
    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("accepted", "Accepted"),
        ("declined", "Declined"),
    ]
    player = models.ForeignKey(User, on_delete=models.CASCADE, related_name="join_requests")
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="join_requests")
    message = models.TextField(blank=True)
    initiated_by_team = models.BooleanField(default=False)
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.player} -> {self.team} ({self.status})"


class MatchGoal(models.Model):
    """A scorer entry for a completed match - who scored, for which side, how many."""
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name="goals")
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="match_goals")
    scorer = models.ForeignKey(User, on_delete=models.CASCADE, related_name="goals_scored")
    goals = models.PositiveSmallIntegerField(default=1)

    class Meta:
        unique_together = ("match", "scorer")
        ordering = ["-goals"]

    def __str__(self):
        return f"{self.scorer} - {self.goals} goal(s) ({self.match})"


class PlayerRating(models.Model):
    """A 1-10 performance rating for a player in a specific completed match."""
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name="ratings")
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name="match_ratings")
    player = models.ForeignKey(User, on_delete=models.CASCADE, related_name="match_ratings")
    rating = models.PositiveSmallIntegerField(default=6)

    class Meta:
        unique_together = ("match", "player")

    def __str__(self):
        return f"{self.player} rated {self.rating}/10 ({self.match})"