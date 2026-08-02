from django.contrib import admin

from .models import (Availability, Conversation, Match, MatchGoal, MatchRequest,
					 Message, Notification, PlayerConversation, PlayerMessage,
					 PlayerRating, Team, TeamJoinRequest, TeamMembership)

admin.site.register(Team)
admin.site.register(TeamMembership)
admin.site.register(Availability)
admin.site.register(MatchRequest)
admin.site.register(Match)
admin.site.register(Conversation)
admin.site.register(Message)
admin.site.register(PlayerConversation)
admin.site.register(PlayerMessage)
admin.site.register(Notification)
admin.site.register(TeamJoinRequest)
admin.site.register(MatchGoal)
admin.site.register(PlayerRating)
