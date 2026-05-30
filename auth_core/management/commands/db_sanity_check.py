from django.core.management.base import BaseCommand
from django.db import connection
from django.apps import apps


class Command(BaseCommand):
    help = "Performs DB sanity checks (connection, tables, migrations, schema)"

    def handle(self, *args, **kwargs):
        self.stdout.write("\n=== DB SANITY CHECK START ===\n")

        self.check_connection()
        self.check_database_identity()
        self.check_migrations()
        self.check_feedback_table()

        self.stdout.write("\n=== DB SANITY CHECK COMPLETE ===\n")

    # 1. Connection test
    def check_connection(self):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1;")
                row = cursor.fetchone()

            self.stdout.write(self.style.SUCCESS("[OK] DB Connection active"))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f"[FAIL] DB Connection error: {e}"))

    # 2. Identify DB (VERY IMPORTANT for Neon vs local)
    def check_database_identity(self):
        try:
            with connection.cursor() as cursor:
                cursor.execute("SELECT current_database();")
                db_name = cursor.fetchone()[0]

                cursor.execute("SELECT inet_server_addr();")
                host = cursor.fetchone()[0]

            self.stdout.write(self.style.WARNING(f"[INFO] Database Name: {db_name}"))
            self.stdout.write(self.style.WARNING(f"[INFO] Server IP: {host}"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"[FAIL] DB identity check failed: {e}"))

    # 3. Migration status check
    def check_migrations(self):
        self.stdout.write("\n[MIGRATIONS STATUS]")

        try:
            for app_config in apps.get_app_configs():
                app_label = app_config.label
                if app_label in ["admin", "auth", "contenttypes", "sessions"]:
                    continue

                self.stdout.write(f"\nApp: {app_label}")

                # show applied migrations
                from django.db.migrations.recorder import MigrationRecorder
                recorder = MigrationRecorder(connection)
                applied = recorder.applied_migrations()

                count = 0
                for m in applied:
                    if m[0] == app_label:
                        count += 1

                self.stdout.write(f"  Applied migrations: {count}")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"[FAIL] Migration check failed: {e}"))

    # 4. Critical table + column check (YOUR ISSUE FIX)
    def check_feedback_table(self):
        self.stdout.write("\n[FEEDBACK TABLE CHECK]")

        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    SELECT column_name
                    FROM information_schema.columns
                    WHERE table_name = 'feedback_feedback';
                """)
                columns = [row[0] for row in cursor.fetchall()]

            required_columns = [
                "id",
                "student_id",
                "type",
                "message",
                "submitted_at",
            ]

            missing = [col for col in required_columns if col not in columns]

            if not missing:
                self.stdout.write(self.style.SUCCESS("[OK] Feedback table schema is correct"))
            else:
                self.stdout.write(self.style.ERROR(f"[MISSING] Columns: {missing}"))

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"[FAIL] Feedback check failed: {e}"))
