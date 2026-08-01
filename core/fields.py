from django.db import models

from .crypto import decrypt_text, encrypt_text


class EncryptedTextField(models.TextField):
    """
    A TextField that is encrypted at rest. Reading model_instance.field
    always gives you the plaintext - encryption/decryption happens
    automatically on the way in/out of the database, so views, templates
    and forms don't need to know about it.
    """

    def from_db_value(self, value, expression, connection):
        return decrypt_text(value)

    def get_prep_value(self, value):
        value = super().get_prep_value(value)
        return encrypt_text(value)
