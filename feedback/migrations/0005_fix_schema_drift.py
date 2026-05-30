from django.db import migrations


class Migration(migrations.Migration):
    """
    One-off migration to fix Neon DB schema drift caused by fake-applied migrations.

    Problem 1: submitted_at exists in Django migration state but not in Neon DB.
    Problem 2: teacher_id exists in Neon DB but model/state expects target_teacher_id.

    SeparateDatabaseAndState is used for both:
      - database_operations → actually executes SQL on Neon
      - state_operations    → empty, because Django state is already correct
    """

    dependencies = [
        ('feedback', '0004_alter_feedback_options'),
    ]

    operations = [

        # ── Fix 1: Rename physical column teacher_id → target_teacher_id ─────
        # Django migration state already considers this field 'target_teacher'.
        # Only the DB column name is wrong.
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        ALTER TABLE feedback_feedback
                        RENAME COLUMN teacher_id TO target_teacher_id;
                    """,
                    reverse_sql="""
                        ALTER TABLE feedback_feedback
                        RENAME COLUMN target_teacher_id TO teacher_id;
                    """,
                ),
            ],
            state_operations=[],
        ),

        # ── Fix 2: Add submitted_at column that DB is missing ─────────────────
        # Django migration state already knows about this column.
        # The physical column was simply never created on Neon.
        # DEFAULT NOW() handles any existing rows safely.
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        ALTER TABLE feedback_feedback
                        ADD COLUMN IF NOT EXISTS submitted_at
                        TIMESTAMPTZ NOT NULL DEFAULT NOW();
                    """,
                    reverse_sql="""
                        ALTER TABLE feedback_feedback
                        DROP COLUMN IF EXISTS submitted_at;
                    """,
                ),
            ],
            state_operations=[],
        ),

    ]
