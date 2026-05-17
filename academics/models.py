from django.db import models
from django.conf import settings

class Faculty(models.Model):
    name = models.CharField(
        max_length=100,
        help_text="Science",
    )
    code = models.CharField(
        max_length=20,
        unique=True,
        help_text="e.g. BSC_CS, BBA",
    )
    description = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)


    class Meta:
        ordering = ["name"]

''' @property
    def total_semesters(self) -> int:
        """Pure arithmetic on own fields — not business logic."""
        return self.duration_years * self.semesters_per_year

    def __str__(self):
        return f{self.code} — {self.name}'''


class Routine(models.Model):
    class Day(models.IntegerChoices):
        SUNDAY    = 0, "Sunday"
        MONDAY    = 1, "Monday"
        TUESDAY   = 2, "Tuesday"
        WEDNESDAY = 3, "Wednesday"
        THURSDAY  = 4, "Thursday"
        FRIDAY    = 5, "Friday"
        SATURDAY  = 6, "Saturday"

    subject = models.ForeignKey('subjects.Subject', on_delete=models.CASCADE, related_name="class_routine")
    section = models.CharField(
        max_length=10,
        blank=True,
        help_text="Section label if the cohort is split, e.g. A, B",
    )
    day_of_week = models.IntegerField(choices=Day.choices)
    start_time = models.TimeField()
    end_time = models.TimeField()
    room = models.CharField(
        max_length=50,
        help_text="Room number or lab name",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Deactivate rather than delete when a slot is removed",
    )

    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)


    '''class Meta:
        ordering = ["day_of_week", "start_time"]
        unique_together = ("room", "day_of_week", "start_time")
        verbose_name = "Class Routine"
        verbose_name_plural = "Class Routines"

    def __str__(self):
        return (
            f"{self.get_day_of_week_display()} "
            f"{self.start_time:%H:%M}-{self.end_time:%H:%M} | "
            f"{self.subject.code} | Room {self.room}"
        )
    '''
    
class ExamRoutine(models.Model):
    class ExamType(models.TextChoices):
        INTERNAL  = "internal",  "Internal Assessment"
        MIDTERM   = "midterm",   "Midterm"
        FINAL     = "final",     "Final Exam"
        PRACTICAL = "practical", "Practical"
        VIVA      = "viva",      "Viva / Oral"


    subject = models.ForeignKey('subjects.Subject', on_delete=models.CASCADE, related_name= "Exam_Routine")
    exam_type = models.CharField(
        max_length=10,
        choices=ExamType.choices,
    )
    exam_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    room = models.CharField(
        max_length=100,
        help_text="Exam hall or room",
    )

    # Overrides Subject.full_marks/pass_marks for this specific sitting
    # e.g. internal exam out of 20, practical out of 25
    full_marks = models.PositiveSmallIntegerField()
    pass_marks = models.PositiveSmallIntegerField()

    notes = models.TextField(
        blank=True,
        help_text="e.g. Open book, bring scientific calculator",
    )

    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

'''    class Meta:
        ordering = ["exam_date", "start_time"]
        unique_together = ("subject", "exam_type", "exam_date")
        verbose_name = "Exam Routine"
        verbose_name_plural = "Exam Routines"

    def __str__(self):
        return (
            f"{self.subject.code} | "
            f"{self.get_exam_type_display()} | "
            f"{self.exam_date}"
        ) '''

class Result(models.Model):

    class Grade(models.TextChoices):
        A_PLUS = "A+", "A+"
        A      = "A",  "A"
        B_PLUS = "B+", "B+"
        B      = "B",  "B"
        C_PLUS = "C+", "C+"
        C      = "C",  "C"
        D      = "D",  "D"
        F      = "F",  "F (Fail)"
        NG     = "NG", "Not Graded"

    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="results",
    )
    exam_routine = models.ForeignKey(
        ExamRoutine,
        on_delete=models.PROTECT,
        related_name="results",
    )

    marks_obtained = models.DecimalField(
        max_digits=6,
        decimal_places=2,
    )
    grade = models.CharField(
        max_length=2,
        choices=Grade.choices,
        blank=True,
        help_text="Set by service layer via compute_grade(); can be manually overridden by admin",
    )

    is_absent = models.BooleanField(
        default=False,
        help_text="True if student was absent; marks_obtained must be 0",
    )
    is_published = models.BooleanField(
        default=False,
        help_text="Student cannot see the result until this is True",
    )

    remarks = models.CharField(
        max_length=200,
        blank=True,
        help_text="e.g. Medical exemption, Withheld, Paper under review",
    )

    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_at = models.DateTimeField(auto_now=True, null=True)

'''    class Meta:
        unique_together = ("student", "exam_routine")
        ordering = ["-exam_routine__exam_date"]

    def __str__(self):
        return (
            f"{self.student} | "
            f"{self.exam_routine.subject.code} | "
            f"{self.marks_obtained}/{self.exam_routine.full_marks} | "
            f"{self.grade or 'Ungraded'}"
        )
        '''