from django.db import migrations


class Migration(migrations.Migration):
    """
    Fixes the FK constraint on feedback_feedback.target_teacher_id.

    Root cause: migration 0002 (which changed the FK target from
    students_teacher to AUTH_USER_MODEL) was fake-applied on Neon.
    The column was renamed in 0005 but the constraint still pointed
    to students_teacher. This migration drops the stale constraint
    and adds the correct one.

    SeparateDatabaseAndState: Django state is already correct (0002
    recorded the AlterField). Only the physical DB constraint is wrong.
    """

    dependencies = [
        ('feedback', '0005_fix_schema_drift'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="""
                        -- Drop the stale FK that points to students_teacher
                        ALTER TABLE feedback_feedback
                        DROP CONSTRAINT IF EXISTS
                            feedback_feedback_teacher_id_fa6efc06_fk_students_teacher_id;

                        -- Add the correct FK pointing to the User table
                        -- Replace 'users_user' below if the shell command above
                        -- printed a different table name
                        ALTER TABLE feedback_feedback
                        ADD CONSTRAINT feedback_feedback_target_teacher_id_fk
                        FOREIGN KEY (target_teacher_id)
                        REFERENCES users_user(id)
                        ON DELETE SET NULL
                        DEFERRABLE INITIALLY DEFERRED;
                    """,
                    reverse_sql="""
                        ALTER TABLE feedback_feedback
                        DROP CONSTRAINT IF EXISTS
                            feedback_feedback_target_teacher_id_fk;

                        ALTER TABLE feedback_feedback
                        ADD CONSTRAINT
                            feedback_feedback_teacher_id_fa6efc06_fk_students_teacher_id
                        FOREIGN KEY (target_teacher_id)
                        REFERENCES students_teacher(id)
                        ON DELETE SET NULL
                        DEFERRABLE INITIALLY DEFERRED;
                    """,
                ),
            ],
            state_operations=[],
        ),
    ]
