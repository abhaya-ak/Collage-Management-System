# feedback/models.py
from django.conf import settings
from django.db import models
from django.utils import timezone

from students.models import Student


class Feedback(models.Model):

    # ── Type choices (tuple kept for migration compatibility — values unchanged)
    TYPE_CHOICES = (
        ('complaint',  'Complaint'),
        ('suggestion', 'Suggestion'),
        ('feedback',   'Feedback'),
    )

    # ── Status lifecycle ──────────────────────────────────────────────────────
    class Status(models.TextChoices):
        PENDING  = 'pending',  'Pending'
        REVIEWED = 'reviewed', 'Under Review'
        RESOLVED = 'resolved', 'Resolved'
        CLOSED   = 'closed',   'Closed'

    # ── Core fields (unchanged) ───────────────────────────────────────────────
    student = models.ForeignKey(
        Student,
        on_delete=models.CASCADE,
    )
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    message = models.TextField()
    submitted_at = models.DateTimeField(default=timezone.now)

    # No related_name on target_teacher — matches migration 0002 exactly
    target_teacher = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    # ── Status + reply fields (Phase B-1, migration 0003) ─────────────────────
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
        help_text="Admin handling state of this feedback item.",
    )
    admin_reply = models.TextField(
        blank=True,
        help_text="Admin response, visible to the submitting student.",
    )
    replied_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When admin first replied.",
    )
    # related_name required — both target_teacher and replied_by point to User
    replied_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='feedback_replies',
        help_text="Admin staff member who replied.",
    )

    class Meta:
        ordering = ['-submitted_at']

    def __str__(self):
        target = (
            f"to {self.target_teacher.first_name}"
            if self.target_teacher
            else "to College"
        )
        return (
            f"{self.get_type_display()} from "
            f"{self.student.roll_no} {target} "
            f"[{self.get_status_display()}]"
        )