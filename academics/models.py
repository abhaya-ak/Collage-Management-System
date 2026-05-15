from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models


# Course
class Course(models.Model):
    """
    A degree programme offered by the college.
    e.g. BSc CS, BBA, BCA

    Referenced by:  Subject, FeeStructure (fees app), Student (users app)
    """

    name = models.CharField(max_length=100, help_text="e.g. Bachelor of Science in Computer Science")
    code = models.CharField(max_length=20, unique=True, help_text="e.g. BSC_CS, BBA")
    duration_years = models.PositiveSmallIntegerField(
        default=4,
        help_text="Total number of years for this programme",
    )
    semesters_per_year = models.PositiveSmallIntegerField(
        default=2,
        help_text="Number of semesters per academic year",
    )
    description = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    @property
    def total_semesters(self) -> int:
        return self.duration_years * self.semesters_per_year

    def __str__(self):
        return f"{self.code} — {self.name}"

# Subject
class Subject(models.Model):
    """
    A single subject/paper taught within a course in a given year and semester.

    The service layer (services.py) enforces:
    - unique code
    - valid teacher FK
    so we don't duplicate that logic in clean().
    """

    name = models.CharField(max_length=150, help_text="e.g. Data Structures and Algorithms")
    code = models.CharField(
        max_length=20,
        unique=True,
        help_text="Short unique code, e.g. CS201",
    )
    course = models.ForeignKey(
        Course,
        on_delete=models.PROTECT,
        related_name="subjects",
    )
    year = models.PositiveSmallIntegerField(help_text="Academic year this subject belongs to")
    semester = models.PositiveSmallIntegerField(help_text="Semester this subject belongs to")

    # Nullable — a subject can exist before a teacher is assigned
    teacher = models.ForeignKey(
        "users.Teacher",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="subjects",
    )

    credit_hours = models.PositiveSmallIntegerField(
        default=3,
        help_text="Credit hours / weight of this subject",
    )
    full_marks = models.PositiveSmallIntegerField(
        default=100,
        help_text="Total marks for this subject",
    )
    pass_marks = models.PositiveSmallIntegerField(
        default=40,
        help_text="Minimum marks required to pass",
    )
    is_elective = models.BooleanField(
        default=False,
        help_text="True if this is an optional elective subject",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["course", "year", "semester", "name"]

    def __str__(self):
        return f"{self.code} — {self.name} ({self.course.code} Y{self.year}S{self.semester})"

# ClassRoutine
class ClassRoutine(models.Model):
    """
    A weekly recurring class slot — the timetable.
    One row = "On Tuesday, 10:00–11:00, Year 1 Sem 1 BSc CS has Data Structures in Room 301."

    Uniqueness: same room cannot be double-booked at the same day+time.
    """

    class Day(models.IntegerChoices):
        SUNDAY = 0, "Sunday"
        MONDAY = 1, "Monday"
        TUESDAY = 2, "Tuesday"
        WEDNESDAY = 3, "Wednesday"
        THURSDAY = 4, "Thursday"
        FRIDAY = 5, "Friday"
        SATURDAY = 6, "Saturday"

    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name="class_routines",
    )

    # Cohort context — who attends this class
    # year + semester is already on Subject, but storing here lets a single subject
    # span multiple cohorts if ever needed (e.g., repeated for different sections)
    section = models.CharField(
        max_length=10,
        blank=True,
        help_text="Section label if the cohort is split, e.g. A, B",
    )

    day_of_week = models.IntegerField(choices=Day.choices)
    start_time = models.TimeField()
    end_time = models.TimeField()
    room = models.CharField(max_length=50, help_text="Room number or lab name")

    is_active = models.BooleanField(
        default=True,
        help_text="Deactivate rather than delete when a slot is removed from schedule",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["day_of_week", "start_time"]
        # Prevent double-booking the same room at the same time on the same day
        unique_together = ("room", "day_of_week", "start_time")
        verbose_name = "Class Routine"
        verbose_name_plural = "Class Routines"

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.start_time and self.end_time and self.start_time >= self.end_time:
            raise ValidationError("Start time must be before end time.")

    def __str__(self):
        return (
            f"{self.get_day_of_week_display()} {self.start_time:%H:%M}–{self.end_time:%H:%M} | "
            f"{self.subject.code} | Room {self.room}"
        )


# ExamRoutine

class ExamRoutine(models.Model):
    """
    A scheduled exam event — one-off, not recurring.
    One row = "Data Structures final exam on 2025-06-15 from 10:00–13:00 in Hall A."
    """

    class ExamType(models.TextChoices):
        INTERNAL = "internal", "Internal Assessment"
        MIDTERM = "midterm", "Midterm"
        FINAL = "final", "Final Exam"
        PRACTICAL = "practical", "Practical"
        VIVA = "viva", "Viva / Oral"

    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name="exam_routines",
    )
    exam_type = models.CharField(max_length=10, choices=ExamType.choices)
    exam_date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    room = models.CharField(max_length=100, help_text="Exam hall or room")

    full_marks = models.PositiveSmallIntegerField(
        help_text="Max marks for this specific exam sitting "
                  "(can differ from Subject.full_marks for internal/practicals)",
    )
    pass_marks = models.PositiveSmallIntegerField()

    notes = models.TextField(
        blank=True,
        help_text="e.g. Open book, bring scientific calculator",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["exam_date", "start_time"]
        # A subject can only have one exam of each type per day
        unique_together = ("subject", "exam_type", "exam_date")
        verbose_name = "Exam Routine"
        verbose_name_plural = "Exam Routines"

    def clean(self):
        from django.core.exceptions import ValidationError

        if self.start_time and self.end_time and self.start_time >= self.end_time:
            raise ValidationError("Start time must be before end time.")

        if self.pass_marks and self.full_marks and self.pass_marks > self.full_marks:
            raise ValidationError("Pass marks cannot exceed full marks.")

    def __str__(self):
        return (
            f"{self.subject.code} | {self.get_exam_type_display()} | {self.exam_date}"
        )



# Result
class Result(models.Model):
    """
    The marks a specific student received in a specific exam.

    One row = "Avay got 78/100 in the Data Structures Final."

    Linked to ExamRoutine (not just Subject) so the result is tied to a
    specific sitting, not just a subject in the abstract.
    """

    class Grade(models.TextChoices):
        A_PLUS = "A+", "A+"
        A = "A", "A"
        B_PLUS = "B+", "B+"
        B = "B", "B"
        C_PLUS = "C+", "C+"
        C = "C", "C"
        D = "D", "D"
        F = "F", "F (Fail)"
        NG = "NG", "Not Graded"

    student = models.ForeignKey(
        "users.Student",
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
        validators=[MinValueValidator(0)],
    )

    # Grade can be auto-computed or manually set by admin
    grade = models.CharField(
        max_length=2,
        choices=Grade.choices,
        blank=True,
        help_text="Leave blank to auto-compute from marks; set manually to override",
    )

    is_absent = models.BooleanField(
        default=False,
        help_text="Mark True if the student was absent; marks_obtained should be 0",
    )
    is_published = models.BooleanField(
        default=False,
        help_text="Result is only visible to the student once published",
    )

    remarks = models.CharField(
        max_length=200,
        blank=True,
        help_text="e.g. Absent, Medical exemption, Withheld",
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        # One result record per student per exam sitting
        unique_together = ("student", "exam_routine")
        ordering = ["-exam_routine__exam_date"]

    @property
    def is_passed(self) -> bool:
        return (
            not self.is_absent
            and self.marks_obtained >= self.exam_routine.pass_marks
        )

    @property
    def percentage(self) -> float:
        full = self.exam_routine.full_marks
        if not full:
            return 0.0
        return round(float(self.marks_obtained) / float(full) * 100, 2)

    def compute_grade(self) -> str:
        """
        Auto-compute grade from percentage.
        Call this in the service layer before saving if grade is not manually set.
        """
        if self.is_absent or not self.is_passed:
            return self.Grade.F

        p = self.percentage
        if p >= 90:
            return self.Grade.A_PLUS
        elif p >= 80:
            return self.Grade.A
        elif p >= 70:
            return self.Grade.B_PLUS
        elif p >= 60:
            return self.Grade.B
        elif p >= 50:
            return self.Grade.C_PLUS
        elif p >= 45:
            return self.Grade.C
        else:
            return self.Grade.D

    def __str__(self):
        return (
            f"{self.student} | {self.exam_routine.subject.code} "
            f"| {self.marks_obtained}/{self.exam_routine.full_marks} | {self.grade}"
        )