import re

from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _


class ComplexPasswordValidator:
    """
    Requires at least one uppercase letter, one digit, and one special
    character. Django's built-in validators (length, common-password list,
    similarity to user info, not-all-numeric) don't check character
    composition at all, so something like "aaaaaaaa" or "myusername1"
    can otherwise sail through as a "valid" password.
    """

    SPECIAL_CHARS_RE = r'[^A-Za-z0-9]'

    def validate(self, password, user=None):
        errors = []
        if not re.search(r'[A-Z]', password):
            errors.append(_("Password must contain at least one uppercase letter."))
        if not re.search(r'\d', password):
            errors.append(_("Password must contain at least one digit."))
        if not re.search(self.SPECIAL_CHARS_RE, password):
            errors.append(_("Password must contain at least one special character (e.g. ! @ # $ % &)."))
        if errors:
            raise ValidationError(errors, code="password_missing_complexity")

    def get_help_text(self):
        return _("Your password must contain at least one uppercase letter, one digit, and one special character.")