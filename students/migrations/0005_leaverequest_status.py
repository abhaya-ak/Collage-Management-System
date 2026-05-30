# students/migrations/0005_leaverequest_status.py
#
# Replaces approved: BooleanField with status: CharField(TextChoices).
# Data migration preserves existing rows:
#   approved=True  → status='approved'
#   approved=False → status='pending'
#
# Safe to run on a live database — adds status first, migrates data,
# then drops approved. All within one transaction.

from django.db import migrations, models


def approved_to_status(apps, schema_editor):
    """Convert existing boolean approved field to status string."""
    LeaveRequest = apps.get_model('students', 'LeaveRequest')
    LeaveRequest.objects.filter(approved=True).update(status='approved')
    # approved=False rows are already status='pending' via default — no update needed


def status_to_approved(apps, schema_editor):
    """Reverse: convert status string back to boolean approved."""
    LeaveRequest = apps.get_model('students', 'LeaveRequest')
    LeaveRequest.objects.filter(status='approved').update(approved=True)
    LeaveRequest.objects.exclude(status='approved').update(approved=False)


class Migration(migrations.Migration):

    dependencies = [
        ('students', '0004_remove_result_student_remove_result_subject_and_more'),
    ]

    operations = [
        # Step 1 — add status column with default 'pending' (all rows get 'pending')
        migrations.AddField(
            model_name='leaverequest',
            name='status',
            field=models.CharField(
                choices=[
                    ('pending',  'Pending'),
                    ('approved', 'Approved'),
                    ('rejected', 'Rejected'),
                ],
                default='pending',
                max_length=10,
                db_index=True,
            ),
        ),
        # Step 2 — data migration: set status='approved' where approved=True
        migrations.RunPython(approved_to_status, reverse_code=status_to_approved),
        # Step 3 — drop the old boolean column
        migrations.RemoveField(
            model_name='leaverequest',
            name='approved',
        ),
    ]
