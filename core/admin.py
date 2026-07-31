from django.contrib import admin
from .models import Team, TeamMembership, Availability, MatchRequest, Match, Conversation, Message, Notification

admin.site.register(Team)
admin.site.register(TeamMembership)
admin.site.register(Availability)
admin.site.register(MatchRequest)
admin.site.register(Match)
admin.site.register(Conversation)
admin.site.register(Message)
admin.site.register(Notification)
