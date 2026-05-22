# academics/serializers.py
from django.utils import timezone
from rest_framework import serializers

from .models import Faculty, Routine, ExamRoutine, Result
from .services import AcademicsService, ResultService


class FacultyReadSerializer(serializers.ModelSerializer):
    """
    Read-only faculty card.
    subject_count gives the frontend a badge without a separate API call.
    """
    subject_count = serializers.SerializerMethodField()

    class Meta:
        model  = Faculty
        fields = [
            'id', 'name', 'description',
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
        fields = ['id', 'name', 'description']
        read_only_fields = ['id']

    def validate_name(self, value):
        try:
            return AcademicsService.validate_faculty_name(value)
        except ValueError as e:
            raise serializers.ValidationError(str(e))

    def to_representation(self, instance):
        return FacultyReadSerializer(instance, context=self.context).data

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
            'day_of_week',   # bonus fix: was accidentally commented out
            'start_time', 'end_time',
            'room',
            'is_active',
        ]
        read_only_fields = ['id']

    def validate(self, attrs):
        def _get(f):
            return attrs.get(f, getattr(self.instance, f, None))
        try:
            AcademicsService.validate_time_range(_get('start_time'), _get('end_time'))
            AcademicsService.validate_room_not_conflicted(
                _get('room'), _get('day_of_week'), _get('start_time'),
                exclude_pk=self.instance.pk if self.instance else None,
            )
        except ValueError as e:
            raise serializers.ValidationError(str(e))
        return attrs

    def to_representation(self, instance):
        return RoutineReadSerializer(instance, context=self.context).data

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

    def validate_exam_date(self, value):
        if not self.instance:
            try:
                AcademicsService.validate_exam_date_not_past(value)
            except ValueError as e:
                raise serializers.ValidationError(str(e))
        return value

    def validate_pass_marks(self, value):
        if value < 1:
            raise serializers.ValidationError("Pass marks must be at least 1.")
        return value

    def validate(self, attrs):
        def _get(f):
            return attrs.get(f, getattr(self.instance, f, None))
        try:
            AcademicsService.validate_marks(_get('full_marks'), _get('pass_marks'))
            AcademicsService.validate_time_range(_get('start_time'), _get('end_time'))
            AcademicsService.validate_unique_exam_sitting(
                _get('subject'), _get('exam_type'), _get('exam_date'),
                exclude_pk=self.instance.pk if self.instance else None,
            )
        except ValueError as e:
            raise serializers.ValidationError(str(e))
        return attrs

    def to_representation(self, instance):
        return ExamRoutineReadSerializer(instance, context=self.context).data


# Result Serializer - student can see published result here
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
        try:
            ResultService.validate_retraction_not_allowed(self.instance, value)
        except ValueError as e:
            raise serializers.ValidationError(str(e))
        return value

    def to_representation(self, instance):
        return ResultAdminReadSerializer(instance, context=self.context).data

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

    def validate(self, attrs):
        def _get(f, default=None):
            return attrs.get(f, getattr(self.instance, f, default))
        try:
            ResultService.validate_absent_marks(_get('is_absent', False), _get('marks_obtained'))
            exam_routine = _get('exam_routine')
            ResultService.validate_marks_in_range(
                _get('marks_obtained'),
                exam_routine.full_marks if exam_routine else None,
                _get('is_absent', False),
            )
            ResultService.validate_unique_result(
                _get('student'), exam_routine,
                exclude_pk=self.instance.pk if self.instance else None,
            )
        except ValueError as e:
            raise serializers.ValidationError(str(e))
        return attrs

    def to_representation(self, instance):
        return ResultAdminReadSerializer(instance, context=self.context).data