import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('feedback', '0002_alter_feedback_target_teacher'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # 1. status — default='pending' fills all existing rows safely
        migrations.AddField(
            model_name='feedback',
            name='status',
            field=models.CharField(
                choices=[
                    ('pending',  'Pending'),
                    ('reviewed', 'Under Review'),
                    ('resolved', 'Resolved'),
                    ('closed',   'Closed'),
                ],
                default='pending',
                db_index=True,
                max_length=20,
                help_text='Admin handling state of this feedback item.',
            ),
        ),
        # 2. admin_reply — blank=True; default='' for existing rows,
        #    preserve_default=False removes default from model state after migration
        migrations.AddField(
            model_name='feedback',
            name='admin_reply',
            field=models.TextField(
                blank=True,
                default='',
                help_text='Admin response, visible to the submitting student.',
            ),
            preserve_default=False,
        ),
        # 3. replied_at — null=True, existing rows get NULL
        migrations.AddField(
            model_name='feedback',
            name='replied_at',
            field=models.DateTimeField(
                blank=True,
                null=True,
                help_text='When admin first replied.',
            ),
        ),
        # 4. replied_by — null=True FK, existing rows get NULL
        migrations.AddField(
            model_name='feedback',
            name='replied_by',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='feedback_replies',
                to=settings.AUTH_USER_MODEL,
                help_text='Admin staff member who replied.',
            ),
        ),
    ]
