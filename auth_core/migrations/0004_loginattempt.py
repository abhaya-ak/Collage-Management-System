# auth_core/migrations/0004_loginattempt.py
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('auth_core', '0003_password_reset_token'),
    ]

    operations = [
        migrations.CreateModel(
            name='LoginAttempt',
            fields=[
                ('id',           models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('username',     models.CharField(db_index=True, max_length=150)),
                ('ip_address',   models.GenericIPAddressField(blank=True, db_index=True, null=True)),
                ('failed_count', models.PositiveSmallIntegerField(default=0)),
                ('locked_until', models.DateTimeField(blank=True, null=True)),
                ('last_attempt', models.DateTimeField(auto_now=True)),
            ],
            options={
                'ordering': ['-last_attempt'],
                'unique_together': {('username', 'ip_address')},
            },
        ),
    ]
