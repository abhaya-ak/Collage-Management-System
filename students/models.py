from django.db import models
from users.models import User
from subjects.models import Subject
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


class Routine(models.Model):
    DAY_CHOICES = (
        ('monday', 'Monday'),
        ('tuesday', 'Tuesday'),
        ('wednesday', 'Wednesday'),
        ('thursday', 'Thursday'),
        ('friday', 'Friday'),
        ('saturday', 'Saturday'),
        ('sunday', 'Sunday'),
    )
    # Here we use CASCADE. If a Subject is completely removed from the curriculum, 
    # all its timetable slots should automatically be destroyed too.
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    day = models.CharField(max_length=15, choices=DAY_CHOICES)
    start_time = models.TimeField()
    end_time = models.TimeField()  
    def __str__(self):
        return f"{self.subject.name} - {self.get_day_display()} ({self.start_time} to {self.end_time})"

'''
class ExamRoutine(models.Model):
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    exam_date = models.DateField()
    start_time = models.TimeField()

    def __str__(self):
        return f"{self.subject.name} Exam on {self.exam_date}"
'''  


# 7) Result
'''class Result(models.Model):
    # If a student or subject is removed, their specific results should also be removed
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    
    marks = models.FloatField()
    grade = models.CharField(max_length=5)

    def __str__(self):
        return f"{self.student.user.first_name} - {self.subject.name} ({self.grade})"
        '''

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