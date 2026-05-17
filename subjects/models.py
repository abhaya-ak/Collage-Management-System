# subjects/models.py
from django.db import models 

class Subject(models.Model):

    teacher = models.ForeignKey(
    'students.Teacher',
    on_delete=models.SET_NULL,  # teacher deleted → subject stays, teacher = null
    related_name="subjects",    # lowercase — Python convention
    null=True,                  # required since SET_NULL needs it
    blank=True,
    )
    name = models.CharField(
    max_length=150,
    null=True,      # temporary - remove after migration
    blank=True,     # temporary - remove after migration
)
    code = models.CharField(
    max_length=20,
    unique=True,
    null=True,      # temporary - remove after migration
    blank=True,     # temporary - remove after migration
    help_text="Short unique code, e.g. CS201",
    )
    faculty = models.ForeignKey(
    'academics.Faculty',
    on_delete=models.CASCADE,
    null=True,      # temporary - remove after migration
    blank=True,     # temporary - remove after migration
    )

    # Nullable — a subject can exist before a teacher is assigned

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

    '''class Meta:
        ordering = ["course", "year", "semester", "name"]

    def __str__(self):
        return f"{self.code} — {self.name} ({self.course.code} Y{self.year}S{self.semester}'''