from django.db import models 
from students.models import Student 

class Feedback(models.Model):
    TYPE_CHOICES = (
        ('complaint', 'Complaint'),
        ('suggestion', 'Suggestion'),
        ('feedback', 'Feedback'),
    )

    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    # teacher is nullable because a student might be leaving feedback about the college itself
    teacher = models.ForeignKey('students.Teacher', on_delete=models.SET_NULL, null=True, blank=True)
    
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    message = models.TextField()

    def __str__(self):
        target = f"to {self.teacher.user.first_name}" if self.teacher else "to College"
        return f"{self.get_type_display()} from {self.student.roll_no} {target}"