"""
Seed the default grade scale (configurable later via admin/API).
Idempotent — safe to run repeatedly.

    python manage.py seed_grade_scale
"""

from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.exams.models import GradeScale

# grade, min, max, grade_point, is_passing
DEFAULT_SCALE = [
    ("A+", "90.00", "100.00", "4.00", True),
    ("A",  "80.00", "89.99",  "3.60", True),
    ("B+", "70.00", "79.99",  "3.20", True),
    ("B",  "60.00", "69.99",  "2.80", True),
    ("C+", "50.00", "59.99",  "2.40", True),
    ("C",  "40.00", "49.99",  "2.00", True),
    ("D",  "35.00", "39.99",  "1.60", True),
    ("F",  "0.00",  "34.99",  "0.00", False),
]


class Command(BaseCommand):
    help = "Seed the default grade scale."

    @transaction.atomic
    def handle(self, *args, **options):
        for grade, lo, hi, gp, passing in DEFAULT_SCALE:
            obj, created = GradeScale.all_objects.update_or_create(
                grade=grade,
                defaults={
                    "min_marks": Decimal(lo),
                    "max_marks": Decimal(hi),
                    "grade_point": Decimal(gp),
                    "is_passing": passing,
                    "is_deleted": False,
                    "deleted_at": None,
                },
            )
            self.stdout.write(f"{'created' if created else 'updated'}: {grade}")
        self.stdout.write(self.style.SUCCESS(f"Grade scale seeded ({len(DEFAULT_SCALE)} grades)."))
