import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('notices', '0003_alter_notice_options_notice_date_posted_and_more'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        # 1. priority field — default='medium' fills all existing rows safely
        migrations.AddField(
            model_name='notice',
            name='priority',
            field=models.CharField(
                choices=[
                    ('low',    'Low'),
                    ('medium', 'Medium'),
                    ('high',   'High'),
                    ('urgent', 'Urgent'),
                ],
                default='medium',
                max_length=10,
                help_text='Urgency level, independent of notice type.',
            ),
        ),
        # 2. NoticeRead junction table — new model, no existing data affected
        migrations.CreateModel(
            name='NoticeRead',
            fields=[
                ('id', models.BigAutoField(
                    auto_created=True, primary_key=True,
                    serialize=False, verbose_name='ID',
                )),
                ('read_at', models.DateTimeField(auto_now_add=True)),
                ('notice', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='reads',
                    to='notices.notice',
                )),
                ('user', models.ForeignKey(
                    on_delete=django.db.models.deletion.CASCADE,
                    related_name='notice_reads',
                    to=settings.AUTH_USER_MODEL,
                )),
            ],
            options={
                'ordering': ['-read_at'],
            },
        ),
        migrations.AlterUniqueTogether(
            name='noticeread',
            unique_together={('notice', 'user')},
        ),
    ]
