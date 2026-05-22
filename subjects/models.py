# subjects/models.py
from django.db import models 

class Subject(models.Model):
    teacher = models.ForeignKey(
        'students.Teacher',
        on_delete=models.SET_NULL,
        related_name="subjects",
        null=True,              
        blank=True,
    )
    name = models.CharField(max_length=150)
    code = models.CharField(
        max_length=20,
        unique=True,
        default="ISC",             
        help_text="Short unique code, e.g. CS201",
    )
    faculty = models.ForeignKey(
        'academics.Faculty',
        on_delete=models.CASCADE,
        related_name="subjects",
        null=True,                  
        blank=True,                  
    )
    full_marks = models.PositiveSmallIntegerField(
        default=100,
        help_text="Total marks for this subject",
    )
    pass_marks = models.PositiveSmallIntegerField(
        default=40,
        help_text="Minimum marks required to pass",
    )
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

    class Meta:
        ordering = ["faculty", "name"]

    def __str__(self):
        return f"{self.code} — {self.name}"