from django.db import models 
from students.models import Student , Subject

class Attendance(models.Model):
    STATUS_CHOICES = (
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('leave', 'Leave'),
    )
    
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    date = models.DateField()
    status = models.CharField(max_length=15, choices=STATUS_CHOICES)

    def __str__(self):
        return f"{self.student.roll_no} - {self.subject.name} ({self.date}): {self.get_status_display()}"