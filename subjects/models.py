# subjects/models.py
from django.db import models 

class Subject(models.Model):
    name = models.CharField(max_length=200)
    course = models.CharField(max_length=100)

    teacher = models.ForeignKey(
        'students.Teacher',   # ✅ correct because Teacher lives in students app //
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='subjects'
    )

    def __str__(self):
        return f"{self.name} - {self.course}"