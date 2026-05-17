from django.db import models 
from students.models import Student 
from django.conf import settings
from django.utils import timezone

class Feedback(models.Model):
    TYPE_CHOICES = (
        ('complaint', 'Complaint'),
        ('suggestion', 'Suggestion'),
        ('feedback', 'Feedback'),
    )
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    message = models.TextField()
    submitted_at = models.DateTimeField(default=timezone.now)
    target_teacher = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE,  null=True, blank=True)

    def __str__(self):
        target = f"to {self.teacher.user.first_name}" if self.teacher else "to College"
        return f"{self.get_type_display()} from {self.student.roll_no} {target}"