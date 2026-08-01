from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0002_notification_user_alter_message_text_and_more'),
    ]

    operations = [
        migrations.AddField(
            model_name='teamjoinrequest',
            name='initiated_by_team',
            field=models.BooleanField(default=False),
        ),
    ]
