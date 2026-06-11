"""
Sprint 6 — Students domain.

Three models, separated by concern:
    Student            -> identity + profile  (NOT academic state)
    StudentDocument    -> uploaded documents
    StudentEnrollment  -> academic state (year/program/semester/section)

Rule: a student may have MANY enrollments historically, but only ONE active
enrollment at a time (enforced by a partial unique constraint).
"""

from django.conf import settings
from django.db import models

from apps.academics.models import AcademicYear, Program, Section, Semester
from apps.core.enums import (
    DocumentType,
    EnrollmentStatus,
    Gender,
    StudentStatus,
)
from apps.core.models import BaseModel, SoftDeleteMixin
from apps.core.validators import (
    validate_document,
    validate_image,
    validate_phone_number,
)


# =============================================================
# Model 1 — Student  (identity + profile)
# =============================================================
class Student(BaseModel, SoftDeleteMixin):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="student",
    )

    student_id = models.CharField(max_length=30, unique=True)
    registration_number = models.CharField(max_length=50, unique=True)

    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100)

    gender = models.CharField(max_length=10, choices=Gender.choices)
    date_of_birth = models.DateField()

    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, blank=True, validators=[validate_phone_number])

    address = models.TextField(blank=True)
    admission_date = models.DateField()

    profile_photo = models.ImageField(
        upload_to="students/photos/", blank=True, null=True, validators=[validate_image]
    )

    status = models.CharField(
        max_length=20, choices=StudentStatus.choices, default=StudentStatus.ACTIVE
    )

    class Meta:
        verbose_name = "Student"
        verbose_name_plural = "Students"
        ordering = ["student_id"]

    def __str__(self):
        return f"{self.student_id} - {self.full_name}"

    @property
    def full_name(self):
        parts = [self.first_name, self.middle_name, self.last_name]
        return " ".join(p for p in parts if p)


# =============================================================
# Model 2 — StudentDocument
# =============================================================
class StudentDocument(BaseModel, SoftDeleteMixin):
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="documents"
    )
    document_type = models.CharField(max_length=30, choices=DocumentType.choices)
    file = models.FileField(upload_to="students/documents/", validators=[validate_document])
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Student Document"
        verbose_name_plural = "Student Documents"
        ordering = ["-uploaded_at"]

    def __str__(self):
        return f"{self.student.student_id} - {self.get_document_type_display()}"


# =============================================================
# Model 3 — StudentEnrollment  (academic state)
# =============================================================
class StudentEnrollment(BaseModel, SoftDeleteMixin):
    student = models.ForeignKey(
        Student, on_delete=models.CASCADE, related_name="enrollments"
    )
    academic_year = models.ForeignKey(
        AcademicYear, on_delete=models.PROTECT, related_name="enrollments"
    )
    program = models.ForeignKey(
        Program, on_delete=models.PROTECT, related_name="enrollments"
    )
    semester = models.ForeignKey(
        Semester, on_delete=models.PROTECT, related_name="enrollments"
    )
    section = models.ForeignKey(
        Section, on_delete=models.PROTECT, related_name="enrollments"
    )

    status = models.CharField(
        max_length=20,
        choices=EnrollmentStatus.choices,
        default=EnrollmentStatus.ACTIVE,
    )
    enrollment_date = models.DateField()

    class Meta:
        verbose_name = "Student Enrollment"
        verbose_name_plural = "Student Enrollments"
        ordering = ["-enrollment_date"]
        constraints = [
            # A student may have many enrollments, but only ONE active at a time.
            models.UniqueConstraint(
                fields=["student"],
                condition=models.Q(status="ACTIVE", is_deleted=False),
                name="unique_active_enrollment_per_student",
            )
        ]

    def __str__(self):
        return (
            f"{self.student.student_id} @ {self.program.code} "
            f"Sem{self.semester.number} [{self.status}]"
        )
