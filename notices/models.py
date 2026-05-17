# notices/models.py
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

    title           = models.CharField(max_length=255)
    type            = models.CharField(
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
    date_posted     = models.DateTimeField(auto_now_add=True, null=True, blank=True )
    is_active       = models.BooleanField(
                        default=True,
                        help_text="Deactivate instead of deleting old notices",
                      )
    class Meta:
        ordering = ['-date_posted']

    def __str__(self):
        return f"[{self.get_type_display()}] [{self.get_target_audience_display()}] {self.title}"
    