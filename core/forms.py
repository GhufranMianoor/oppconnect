from django import forms

from .models import Availability, MatchRequest, Message, Team, TeamJoinRequest


class TeamForm(forms.ModelForm):
    class Meta:
        model = Team
        fields = ["name", "logo", "bio", "home_ground", "city", "level", "playstyle"]
        widgets = {
            "bio": forms.Textarea(attrs={"rows": 3, "placeholder": "Tell other teams about your squad..."}),
        }


class MatchRequestForm(forms.ModelForm):
    class Meta:
        model = MatchRequest
        fields = ["proposed_date", "proposed_time", "venue", "message"]
        widgets = {
            "proposed_date": forms.DateInput(attrs={"type": "date"}),
            "proposed_time": forms.TimeInput(attrs={"type": "time"}),
            "message": forms.Textarea(attrs={"rows": 3, "placeholder": "Add a note (optional)"}),
        }


class OpenMatchRequestForm(forms.ModelForm):
    """Used for 'Create Request' where no opponent is picked yet - posts publicly."""
    class Meta:
        model = MatchRequest
        fields = ["proposed_date", "proposed_time", "venue", "message"]
        widgets = {
            "proposed_date": forms.DateInput(attrs={"type": "date"}),
            "proposed_time": forms.TimeInput(attrs={"type": "time"}),
            "message": forms.Textarea(attrs={"rows": 3, "placeholder": "Describe the kind of opponent you're looking for..."}),
        }


class AvailabilityForm(forms.ModelForm):
    class Meta:
        model = Availability
        fields = ["date", "status"]
        widgets = {"date": forms.DateInput(attrs={"type": "date"})}


class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ["text"]
        widgets = {"text": forms.TextInput(attrs={"placeholder": "Type a message...", "autocomplete": "off"})}


class TeamJoinRequestForm(forms.ModelForm):
    class Meta:
        model = TeamJoinRequest
        fields = ["message"]
        widgets = {
            "message": forms.Textarea(attrs={"rows": 3, "placeholder": "Tell the captain why you'd be a good fit (position, experience...)"}),
        }


class TeamSearchForm(forms.Form):
    q = forms.CharField(required=False, label="Search")
    level = forms.ChoiceField(required=False, choices=[("", "Any Level")] + Team._meta.get_field("level").choices)
    playstyle = forms.ChoiceField(required=False, choices=[("", "Any Playstyle")] + Team._meta.get_field("playstyle").choices)
    city = forms.CharField(required=False)
