from django.contrib.auth.models import AbstractUser
from django.db import models

POSITION_CHOICES = [
    ("GK", "Goalkeeper"),
    ("DEF", "Defender"),
    ("MID", "Midfielder"),
    ("FWD", "Forward"),
]


class User(AbstractUser):
    """A registered user. Every user can captain/manage one Team profile."""
    phone = models.CharField(max_length=20, blank=True)
    city = models.CharField(max_length=100, blank=True, default="Karachi")
    avatar = models.ImageField(upload_to="avatars/", blank=True, null=True)
    position = models.CharField(max_length=3, choices=POSITION_CHOICES, blank=True)
    bio = models.TextField(blank=True)

    def __str__(self):
        return self.get_full_name() or self.username

    @property
    def initials(self):
        name = self.get_full_name() or self.username
        parts = name.split()
        if len(parts) >= 2:
            return (parts[0][0] + parts[1][0]).upper()
        return name[:2].upper()
