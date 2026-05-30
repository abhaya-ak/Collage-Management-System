from django.db import models
from django.conf import settings

class Student(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    roll_no = models.CharField(max_length=50, unique=True)
    course = models.CharField(max_length=100)
    year = models.IntegerField()
    section = models.CharField(max_length=10)
    def __str__(self):
        return f"{self.user.first_name} {self.user.last_name} ({self.roll_no})"

class Teacher(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    department = models.CharField(max_length=100)
    
    def __str__(self):
        return f"Prof. {self.user.first_name} {self.user.last_name}"
             

# 9) LeaveRequest
class LeaveRequest(models.Model):

    class Status(models.TextChoices):
        PENDING  = 'pending',  'Pending'
        APPROVED = 'approved', 'Approved'
        REJECTED = 'rejected', 'Rejected'

    student   = models.ForeignKey(Student, on_delete=models.CASCADE)
    from_date = models.DateField()
    to_date   = models.DateField()
    reason    = models.TextField()

    # Three-state status:
    #   pending  — awaiting admin review (default)
    #   approved — admin accepted the request
    #   rejected — admin explicitly declined (was indistinguishable from pending with bool)
    status = models.CharField(
        max_length=10,
        choices=Status.choices,
        default=Status.PENDING,
        db_index=True,
    )

    def __str__(self):
        return (
            f"Leave: {self.student.roll_no} "
            f"({self.from_date} to {self.to_date}) - {self.get_status_display()}"
        )