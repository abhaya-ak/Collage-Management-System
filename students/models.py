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
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    from_date = models.DateField()
    to_date = models.DateField()
    reason = models.TextField()
    
    # We use a BooleanField with a default of False, meaning leaves are 
    # automatically considered "Pending" or "Not Approved" until an admin changes it.
    approved = models.BooleanField(default=False)

    def __str__(self):
        status = "Approved" if self.approved else "Pending"
        return f"Leave: {self.student.roll_no} ({self.from_date} to {self.to_date}) - {status}"