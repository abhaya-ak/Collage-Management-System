from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        # Must follow the migration that established the full Attendance model
        # with unique_together, created_at, and marked_by fields.
        ('attendance', '0003_alter_attendance_options_attendance_created_at_and_more'),
    ]

    operations = [
        migrations.AlterField(
            model_name='attendance',
            name='status',
            field=models.CharField(
                # max_length=15 is unchanged — 'late' is only 4 chars.
                max_length=15,
                choices=[
                    ('present', 'Present'),
                    ('absent',  'Absent'),
                    ('leave',   'Leave'),
                    # F-AT-05: LATE added. Counts as present for % calculation (Option A).
                    ('late',    'Late'),
                ],
            ),
        ),
    ]
