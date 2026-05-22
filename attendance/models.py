# attendance/models.py
from django.db import models
from django.conf import settings

class Attendance(models.Model):
    class Status(models.TextChoices):
        PRESENT = 'present', 'Present'
        ABSENT  = 'absent',  'Absent'
        LEAVE   = 'leave',   'Leave'

    student   = models.ForeignKey(
        'students.Student',
        on_delete=models.CASCADE,
        related_name='attendance_records',
    )
    subject   = models.ForeignKey(
        'subjects.Subject',
        on_delete=models.CASCADE,
        related_name='attendance_records',
    )
    date      = models.DateField()
    status    = models.CharField(
        max_length=15,
        choices=Status.choices,
    )
    marked_by = models.ForeignKey(       # was the broken anonymous FK
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,       # teacher deleted → record stays
        null=True,
        blank=True,
        related_name='marked_attendances',
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True)

    class Meta:
        # One record per student per subject per day — no duplicates
        unique_together = ('student', 'subject', 'date')
        ordering        = ['-date']

    def __str__(self):
        return (
            f"{self.student.roll_no} | {self.subject.code} | "
            f"{self.date} | {self.get_status_display()}"
        )