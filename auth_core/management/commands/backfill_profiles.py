from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model

from auth_core.models import UserProfile
from students.models import Student, Teacher
from users.models import UserRole
from users.constants import RoleNames

User = get_user_model()


class Command(BaseCommand):
    help = "Backfills missing UserProfile and Teacher rows for existing users."

    def handle(self, *args, **kwargs):
        self.stdout.write("\n=== BACKFILL START ===\n")

        self._backfill_user_profiles()
        self._backfill_teacher_profiles()
        self._report_missing_student_profiles()

        self.stdout.write("\n=== BACKFILL COMPLETE ===\n")

    def _backfill_user_profiles(self):
        self.stdout.write("[1/3] UserProfile backfill...")
        for user in User.objects.all():
            _, created = UserProfile.objects.get_or_create(user=user)
            tag = self.style.SUCCESS("[CREATED]") if created else "[EXISTS] "
            self.stdout.write(f"  {tag} UserProfile → {user.username}")

    def _backfill_teacher_profiles(self):
        self.stdout.write("\n[2/3] Teacher profile backfill...")
        qs = UserRole.objects.filter(
            role__name=RoleNames.TEACHER
        ).select_related('user')

        if not qs.exists():
            self.stdout.write("  No users with teacher role found.")
            return

        for ur in qs:
            t, created = Teacher.objects.get_or_create(
                user=ur.user,
                defaults={'department': 'Unassigned'},
            )
            if created:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"  [CREATED] Teacher → {ur.user.username} (pk={t.pk})"
                        f" — update dept via PATCH /api/v1/students/teachers/{t.pk}/"
                    )
                )
            else:
                self.stdout.write(
                    f"  [EXISTS]  Teacher → {ur.user.username} | dept={t.department}"
                )

    def _report_missing_student_profiles(self):
        self.stdout.write("\n[3/3] Student profile gap report...")
        qs = UserRole.objects.filter(
            role__name=RoleNames.STUDENT
        ).select_related('user')

        missing = []
        for ur in qs:
            if not Student.objects.filter(user=ur.user).exists():
                missing.append(ur.user)

        if not missing:
            self.stdout.write(self.style.SUCCESS(
                "  All student-role users have Student profiles."
            ))
        else:
            for user in missing:
                self.stdout.write(self.style.WARNING(
                    f"  [MISSING] {user.username} (pk={user.pk})"
                    f" — create via POST /api/v1/students/profiles/"
                ))
