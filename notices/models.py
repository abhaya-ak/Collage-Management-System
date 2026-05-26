# notices/models.py
from django.conf import settings
from django.db import models


class Notice(models.Model):

    class Type(models.TextChoices):
        FEE       = 'fee',       'Fee'
        EXAM      = 'exam',      'Exam'
        HOLIDAY   = 'holiday',   'Holiday'
        EMERGENCY = 'emergency', 'Emergency'
        GENERAL   = 'general',   'General'

    class Audience(models.TextChoices):
        ALL      = 'all',      'Everyone'
        STUDENTS = 'students', 'Students Only'
        TEACHERS = 'teachers', 'Teachers Only'
        FINANCE  = 'finance',  'Finance Only'

    # ── Priority (Phase B-2) ──────────────────────────────────────────────────
    class Priority(models.TextChoices):
        LOW    = 'low',    'Low'
        MEDIUM = 'medium', 'Medium'
        HIGH   = 'high',   'High'
        URGENT = 'urgent', 'Urgent'

    # ── Core fields (unchanged) ───────────────────────────────────────────────
    title = models.CharField(max_length=255)
    type  = models.CharField(
        max_length=20,
        choices=Type.choices,
        default=Type.GENERAL,
    )
    content         = models.TextField()
    target_audience = models.CharField(
        max_length=20,
        choices=Audience.choices,
        default=Audience.ALL,
    )
    date_posted = models.DateTimeField(auto_now_add=True, null=True, blank=True)
    is_active   = models.BooleanField(
        default=True,
        help_text="Deactivate instead of deleting old notices",
    )

    # ── Priority field (Phase B-2, migration 0004) ───────────────────────────
    priority = models.CharField(
        max_length=10,
        choices=Priority.choices,
        default=Priority.MEDIUM,
        help_text="Urgency level, independent of notice type.",
    )

    class Meta:
        ordering = ['-date_posted']

    def __str__(self):
        return (
            f"[{self.get_type_display()}] "
            f"[{self.get_priority_display()}] "
            f"[{self.get_target_audience_display()}] "
            f"{self.title}"
        )

class NoticeRead(models.Model):
    notice  = models.ForeignKey(
        Notice,
        on_delete=models.CASCADE,
        related_name='reads',
    )
    user    = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='notice_reads',
    )
    read_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('notice', 'user')
        ordering        = ['-read_at']

    def __str__(self):
        return f"{self.user.username} read [{self.notice.title}] at {self.read_at}"