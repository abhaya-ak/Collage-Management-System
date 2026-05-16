# subjects/models.py
from django.db import models 

class Subject(models.Model):

    name = models.CharField(
        max_length=150,
        help_text="",
    )
    code = models.CharField(
        max_length=20,
        unique=True,
        help_text="Short unique code, e.g. CS201",
    )
    faculty = models.ForeignKey('academics.Faculty', on_delete=models.CASCADE)

    # Nullable — a subject can exist before a teacher is assigned
    teacher = models.ForeignKey('students.Teacher', on_delete=models.CASCADE, related_name="Subjects", blank=True)

    full_marks = models.PositiveSmallIntegerField(
        default=100,
        help_text="Total marks for this subject",
    )
    pass_marks = models.PositiveSmallIntegerField(
        default=40,
        help_text="Minimum marks required to pass",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    '''class Meta:
        ordering = ["course", "year", "semester", "name"]

    def __str__(self):
        return f"{self.code} — {self.name} ({self.course.code} Y{self.year}S{self.semester}'''