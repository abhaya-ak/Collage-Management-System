# auth_core/migrations/0005_auditlog_event_max_length.py
"""
Widens AuditLog.event from max_length=30 to max_length=40 to accommodate
new domain audit event codes (e.g. 'fee_bill_generated', 'result_published').

WHY a separate migration (not squashed into 0001):
    - The column already exists in production; altering max_length on a
      VARCHAR is a lightweight DDL on all major databases (Postgres, SQLite,
      MySQL) and does not require a table rewrite.
    - Keeping it isolated makes it easy to review and roll back.
"""
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('auth_core', '0004_loginattempt'),
    ]

    operations = [
        migrations.AlterField(
            model_name='auditlog',
            name='event',
            field=models.CharField(
                max_length=40,
                choices=[
                    # Auth
                    ('register',               'User Registered'),
                    ('login',                  'Login Success'),
                    ('login_failed',           'Login Failed'),
                    ('logout',                 'Logout'),
                    ('token_refresh',          'Token Refreshed'),
                    ('password_change',        'Password Changed'),
                    ('token_blacklisted',      'Token Blacklisted'),
                    ('password_reset_request', 'Password Reset Requested'),
                    ('password_reset_confirm', 'Password Reset Confirmed'),
                    # Fees
                    ('fee_bill_generated',     'Fee Bill Generated'),
                    ('payment_submitted',      'Payment Submitted'),
                    ('payment_verified',       'Payment Verified'),
                    ('payment_rejected',       'Payment Rejected'),
                    # Academics
                    ('result_published',       'Result Published'),
                    ('result_deleted',         'Result Soft-Deleted'),
                ],
                db_index=True,
            ),
        ),
    ]
