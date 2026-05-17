# academics/serializers.py
from django.utils import timezone
from rest_framework import serializers

from .models import Faculty, Routine, ExamRoutine, Result


# ===========================================================================
# FACULTY
# ===========================================================================

class FacultyReadSerializer(serializers.ModelSerializer):
    """
    Read-only faculty card.
    subject_count gives the frontend a badge without a separate API call.
    """
    subject_count = serializers.SerializerMethodField()

    class Meta:
        model  = Faculty
        fields = [
            'id', 'name', 'code', 'description',
            'subject_count',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields

    def get_subject_count(self, obj):
        # uses the reverse relation from Subject.faculty FK
        return obj.subjects.count()


class FacultyWriteSerializer(serializers.ModelSerializer):
    """
    Admin creates or updates a faculty.
    Code is normalized to uppercase and checked for uniqueness with a
    readable error instead of a raw DB IntegrityError.
    """

    class Meta:
        model  = Faculty
        fields = ['id', 'name', 'code', 'description']
        read_only_fields = ['id']

    def validate_name(self, value):
        value = value.strip()
        if len(value) < 2:
            raise serializers.ValidationError(
                "Faculty name must be at least 2 characters."
            )
        return value

    def validate_code(self, value):
        value = value.strip().upper()   # BSC_CS, BBA — always uppercase
        if not value:
            raise serializers.ValidationError("Code cannot be blank.")

        qs = Faculty.objects.filter(code=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                f"A faculty with code '{value}' already exists."
            )
        return value

    def to_representation(self, instance):
        return FacultyReadSerializer(instance, context=self.context).data


# ===========================================================================
# ROUTINE (class timetable)
# ===========================================================================

class RoutineReadSerializer(serializers.ModelSerializer):
    """
    Class schedule card. Integer day resolved to label.
    All FK fields resolved to human-readable strings.
    """
    subject_name = serializers.CharField(
        source='subject.name', read_only=True
    )
    subject_code = serializers.CharField(
        source='subject.code', read_only=True
    )
    faculty_name = serializers.CharField(
        source='subject.faculty.name', read_only=True
    )
    teacher_name = serializers.SerializerMethodField()
    day          = serializers.CharField(
        source='get_day_of_week_display', read_only=True
    )

    class Meta:
        model  = Routine
        fields = [
            'id',
            'subject', 'subject_name', 'subject_code', 'faculty_name',
            'teacher_name',
            'day', 'day_of_week',    # both: label for display, int for sorting
            'section',
            'start_time', 'end_time',
            'room',
            'is_active',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields

    def get_teacher_name(self, obj):
        t = obj.subject.teacher
        if not t:
            return None
        return f"{t.user.first_name} {t.user.last_name}".strip()


class RoutineWriteSerializer(serializers.ModelSerializer):
    """
    Admin creates or updates a timetable slot.
    Validates: time range, room conflict, duplicate slot.
    """

    class Meta:
        model  = Routine
        fields = [
            'id',
            'subject', 'section',
            'day_of_week',
            'start_time', 'end_time',
            'room',
            'is_active',
        ]
        read_only_fields = ['id']

    # --- Object-level ------------------------------------------------------

    def validate(self, attrs):
        self._validate_time_range(attrs)
        self._validate_room_conflict(attrs)
        return attrs

    def _validate_time_range(self, attrs):
        start = attrs.get('start_time', getattr(self.instance, 'start_time', None))
        end   = attrs.get('end_time',   getattr(self.instance, 'end_time',   None))

        if start and end and end <= start:
            raise serializers.ValidationError({
                'end_time': "End time must be after start time."
            })

    def _validate_room_conflict(self, attrs):
        """
        Same room cannot have two classes at the same time on the same day.
        Mirrors the commented-out unique_together in the model Meta —
        catches it before the DB and returns a readable message.
        """
        room        = attrs.get('room',        getattr(self.instance, 'room',        None))
        day_of_week = attrs.get('day_of_week', getattr(self.instance, 'day_of_week', None))
        start_time  = attrs.get('start_time',  getattr(self.instance, 'start_time',  None))

        qs = Routine.objects.filter(
            room=room,
            day_of_week=day_of_week,
            start_time=start_time,
            is_active=True,
        )
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            day_label = Routine.Day(day_of_week).label if day_of_week is not None else day_of_week
            raise serializers.ValidationError(
                f"Room '{room}' is already booked on {day_label} "
                f"at {start_time}. Choose a different room or time."
            )

    def to_representation(self, instance):
        return RoutineReadSerializer(instance, context=self.context).data


# ===========================================================================
# EXAM ROUTINE
# ===========================================================================

class ExamRoutineReadSerializer(serializers.ModelSerializer):
    """
    Exam schedule card. All codes and choices resolved to labels.
    """
    subject_name      = serializers.CharField(
        source='subject.name', read_only=True
    )
    subject_code      = serializers.CharField(
        source='subject.code', read_only=True
    )
    faculty_name      = serializers.CharField(
        source='subject.faculty.name', read_only=True
    )
    exam_type_display = serializers.CharField(
        source='get_exam_type_display', read_only=True
    )
    pass_percentage   = serializers.SerializerMethodField()

    class Meta:
        model  = ExamRoutine
        fields = [
            'id',
            'subject', 'subject_name', 'subject_code', 'faculty_name',
            'exam_type', 'exam_type_display',
            'exam_date',
            'start_time', 'end_time',
            'room',
            'full_marks', 'pass_marks', 'pass_percentage',
            'notes',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields

    def get_pass_percentage(self, obj):
        """
        Convenience field so the frontend doesn't compute this.
        e.g. 40 / 100 → 40.0
        """
        if obj.full_marks:
            return round((obj.pass_marks / obj.full_marks) * 100, 1)
        return None


class ExamRoutineWriteSerializer(serializers.ModelSerializer):
    """
    Admin schedules an exam sitting.
    Validates: marks logic, time range, no past exam dates on create,
    no duplicate (subject + type + date).
    """

    class Meta:
        model  = ExamRoutine
        fields = [
            'id',
            'subject',
            'exam_type',
            'exam_date',
            'start_time', 'end_time',
            'room',
            'full_marks', 'pass_marks',
            'notes',
        ]
        read_only_fields = ['id']

    # --- Field-level -------------------------------------------------------

    def validate_exam_date(self, value):
        # Block scheduling in the past only on CREATE
        if not self.instance and value < timezone.now().date():
            raise serializers.ValidationError(
                "Exam date cannot be in the past."
            )
        return value

    def validate_pass_marks(self, value):
        if value < 1:
            raise serializers.ValidationError(
                "Pass marks must be at least 1."
            )
        return value

    # --- Object-level ------------------------------------------------------

    def validate(self, attrs):
        self._validate_marks(attrs)
        self._validate_time_range(attrs)
        self._validate_unique_sitting(attrs)
        return attrs

    def _validate_marks(self, attrs):
        full  = attrs.get('full_marks',  getattr(self.instance, 'full_marks',  None))
        _pass = attrs.get('pass_marks',  getattr(self.instance, 'pass_marks',  None))

        if full and _pass and _pass >= full:
            raise serializers.ValidationError({
                'pass_marks': (
                    f"Pass marks ({_pass}) must be strictly less "
                    f"than full marks ({full})."
                )
            })

    def _validate_time_range(self, attrs):
        start = attrs.get('start_time', getattr(self.instance, 'start_time', None))
        end   = attrs.get('end_time',   getattr(self.instance, 'end_time',   None))

        if start and end and end <= start:
            raise serializers.ValidationError({
                'end_time': "End time must be after start time."
            })

    def _validate_unique_sitting(self, attrs):
        """
        Mirrors commented-out unique_together("subject", "exam_type", "exam_date").
        One subject cannot have two sittings of the same type on the same day.
        """
        subject   = attrs.get('subject',   getattr(self.instance, 'subject',   None))
        exam_type = attrs.get('exam_type', getattr(self.instance, 'exam_type', None))
        exam_date = attrs.get('exam_date', getattr(self.instance, 'exam_date', None))

        qs = ExamRoutine.objects.filter(
            subject=subject, exam_type=exam_type, exam_date=exam_date
        )
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            raise serializers.ValidationError(
                f"A '{exam_type}' exam for this subject on {exam_date} "
                "already exists."
            )

    def to_representation(self, instance):
        return ExamRoutineReadSerializer(instance, context=self.context).data


# ===========================================================================
# RESULT — student view (published only)
# ===========================================================================

class ResultStudentReadSerializer(serializers.ModelSerializer):
    """
    What a student sees for their own results.
    Only call this with published results — filter is_published=True in the view.
    """
    subject_name      = serializers.CharField(
        source='exam_routine.subject.name', read_only=True
    )
    subject_code      = serializers.CharField(
        source='exam_routine.subject.code', read_only=True
    )
    exam_type_display = serializers.CharField(
        source='exam_routine.get_exam_type_display', read_only=True
    )
    exam_date         = serializers.DateField(
        source='exam_routine.exam_date', read_only=True
    )
    full_marks        = serializers.IntegerField(
        source='exam_routine.full_marks', read_only=True
    )
    pass_marks        = serializers.IntegerField(
        source='exam_routine.pass_marks', read_only=True
    )
    grade_display     = serializers.CharField(
        source='get_grade_display', read_only=True
    )
    passed            = serializers.SerializerMethodField()

    class Meta:
        model  = Result
        fields = [
            'id',
            'subject_name', 'subject_code',
            'exam_type_display', 'exam_date',
            'marks_obtained', 'full_marks', 'pass_marks',
            'grade', 'grade_display',
            'is_absent',
            'passed',
            'remarks',
        ]
        read_only_fields = fields

    def get_passed(self, obj):
        if obj.is_absent:
            return False
        return obj.marks_obtained >= obj.exam_routine.pass_marks


# ===========================================================================
# RESULT — admin enter / update marks
# ===========================================================================

class ResultWriteSerializer(serializers.ModelSerializer):
    """
    Admin enters or corrects a student's result.

    Grade is intentionally accepted here — admin can override the
    service-layer computed grade (e.g. medical exemption scenarios).
    If left blank, the service layer's compute_grade() fills it post-save.

    is_published is excluded — use ResultPublishSerializer for that action.
    Keeping publish as a separate write path prevents accidental publishing
    while editing marks.
    """

    class Meta:
        model  = Result
        fields = [
            'id',
            'student',
            'exam_routine',
            'marks_obtained',
            'grade',
            'is_absent',
            'remarks',
        ]
        read_only_fields = ['id']

    # --- Object-level ------------------------------------------------------

    def validate(self, attrs):
        self._validate_absent_marks_consistency(attrs)
        self._validate_marks_within_range(attrs)
        self._validate_unique_result(attrs)
        return attrs

    def _validate_absent_marks_consistency(self, attrs):
        is_absent      = attrs.get('is_absent',      getattr(self.instance, 'is_absent',      False))
        marks_obtained = attrs.get('marks_obtained', getattr(self.instance, 'marks_obtained', None))

        if is_absent and marks_obtained and marks_obtained != 0:
            raise serializers.ValidationError({
                'marks_obtained': (
                    "Student is marked absent. "
                    "marks_obtained must be 0 for absent students."
                )
            })

    def _validate_marks_within_range(self, attrs):
        exam_routine   = attrs.get('exam_routine',   getattr(self.instance, 'exam_routine',   None))
        marks_obtained = attrs.get('marks_obtained', getattr(self.instance, 'marks_obtained', None))
        is_absent      = attrs.get('is_absent',      getattr(self.instance, 'is_absent',      False))

        if is_absent:
            return  # already validated above

        if exam_routine and marks_obtained is not None:
            if marks_obtained < 0:
                raise serializers.ValidationError({
                    'marks_obtained': "Marks cannot be negative."
                })
            if marks_obtained > exam_routine.full_marks:
                raise serializers.ValidationError({
                    'marks_obtained': (
                        f"Marks obtained ({marks_obtained}) cannot exceed "
                        f"full marks ({exam_routine.full_marks}) "
                        f"for this exam."
                    )
                })

    def _validate_unique_result(self, attrs):
        """
        Mirrors commented-out unique_together("student", "exam_routine").
        One student → one result per exam sitting.
        """
        student      = attrs.get('student',      getattr(self.instance, 'student',      None))
        exam_routine = attrs.get('exam_routine', getattr(self.instance, 'exam_routine', None))

        qs = Result.objects.filter(student=student, exam_routine=exam_routine)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            raise serializers.ValidationError(
                "A result for this student and exam already exists. "
                "Use the update endpoint to correct it."
            )

    def to_representation(self, instance):
        return ResultAdminReadSerializer(instance, context=self.context).data


# ===========================================================================
# RESULT — admin publishes (separate action, separate serializer)
# ===========================================================================

class ResultPublishSerializer(serializers.ModelSerializer):
    """
    Admin flips is_published to True.
    Deliberately minimal — only one field.

    Why separate from ResultWriteSerializer:
    Publishing is an irreversible business action with visibility consequences.
    Keeping it separate means the view can require an extra permission check,
    and accidental mark edits can never accidentally publish a result.
    """

    class Meta:
        model  = Result
        fields = ['id', 'is_published']
        read_only_fields = ['id']

    def validate_is_published(self, value):
        # Once published, a result cannot be un-published via this endpoint.
        # Retraction is a deliberate admin action that needs its own workflow.
        if self.instance and self.instance.is_published and not value:
            raise serializers.ValidationError(
                "A published result cannot be retracted here. "
                "Contact a system administrator."
            )
        return value

    def to_representation(self, instance):
        return ResultAdminReadSerializer(instance, context=self.context).data


# ===========================================================================
# RESULT — full admin read
# ===========================================================================

class ResultAdminReadSerializer(serializers.ModelSerializer):
    """
    Complete result record for admin screens.
    """
    student_name      = serializers.SerializerMethodField()
    subject_name      = serializers.CharField(
        source='exam_routine.subject.name', read_only=True
    )
    subject_code      = serializers.CharField(
        source='exam_routine.subject.code', read_only=True
    )
    exam_type_display = serializers.CharField(
        source='exam_routine.get_exam_type_display', read_only=True
    )
    exam_date         = serializers.DateField(
        source='exam_routine.exam_date', read_only=True
    )
    full_marks        = serializers.IntegerField(
        source='exam_routine.full_marks', read_only=True
    )
    pass_marks        = serializers.IntegerField(
        source='exam_routine.pass_marks', read_only=True
    )
    grade_display     = serializers.CharField(
        source='get_grade_display', read_only=True
    )
    passed            = serializers.SerializerMethodField()

    class Meta:
        model  = Result
        fields = [
            'id',
            'student', 'student_name',
            'subject_name', 'subject_code',
            'exam_type_display', 'exam_date',
            'marks_obtained', 'full_marks', 'pass_marks',
            'grade', 'grade_display',
            'is_absent',
            'passed',
            'is_published',
            'remarks',
            'created_at', 'updated_at',
        ]
        read_only_fields = fields

    def get_student_name(self, obj):
        return f"{obj.student.first_name} {obj.student.last_name}".strip()

    def get_passed(self, obj):
        if obj.is_absent:
            return False
        return obj.marks_obtained >= obj.exam_routine.pass_marks