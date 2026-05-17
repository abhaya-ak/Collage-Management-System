# students/serializers.py
from rest_framework import serializers
from django.utils import timezone
from .models import Student, Teacher, LeaveRequest
from academics.models import Routine, Result
from attendance.models import Attendance
from notices.models import Notice
from feedback.models import Feedback


# ===========================================================================
# STUDENT
# ===========================================================================

class StudentProfileSerializer(serializers.ModelSerializer):
    """
    Read-only. What the frontend profile screen receives.
    Flattens the related User fields — frontend never sees the raw user ID.
    """
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name  = serializers.CharField(source='user.last_name',  read_only=True)
    email      = serializers.EmailField(source='user.email',     read_only=True)
    username   = serializers.CharField(source='user.username',   read_only=True)

    class Meta:
        model  = Student
        fields = [
            'id', 'username', 'first_name', 'last_name',
            'email', 'roll_no', 'course', 'year', 'section',
        ]
        read_only_fields = fields


class StudentWriteSerializer(serializers.ModelSerializer):
    """
    Used by admin to CREATE or UPDATE a student record.
    Does NOT create the User — user must already exist.
    Returns the full read representation on success.
    """
    class Meta:
        model  = Student
        fields = ['id', 'user', 'roll_no', 'course', 'year', 'section']
        read_only_fields = ['id']

    def validate_user(self, user):
        """One user can only have one student profile."""
        qs = Student.objects.filter(user=user)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                "A student profile already exists for this user."
            )
        return user

    def validate_year(self, value):
        if value < 1:
            raise serializers.ValidationError("Year must be at least 1.")
        return value

    def to_representation(self, instance):
        return StudentProfileSerializer(instance, context=self.context).data


# ===========================================================================
# TEACHER
# ===========================================================================

class TeacherSerializer(serializers.ModelSerializer):
    """
    Read-only teacher card — used wherever teacher info is displayed.
    """
    full_name  = serializers.SerializerMethodField()
    email      = serializers.EmailField(source='user.email',    read_only=True)
    username   = serializers.CharField(source='user.username',  read_only=True)

    class Meta:
        model  = Teacher
        fields = ['id', 'username', 'full_name', 'email', 'department']
        read_only_fields = fields

    def get_full_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}".strip()


# ===========================================================================
# LEAVE REQUEST
# ===========================================================================

class LeaveRequestReadSerializer(serializers.ModelSerializer):
    """
    What students and admins see when listing leave requests.
    """
    student_name = serializers.SerializerMethodField()
    status       = serializers.SerializerMethodField()

    class Meta:
        model  = LeaveRequest
        fields = [
            'id', 'student_name',
            'from_date', 'to_date', 'reason',
            'approved', 'status',
        ]
        read_only_fields = fields

    def get_student_name(self, obj):
        return f"{obj.student.user.first_name} {obj.student.user.last_name}".strip()

    def get_status(self, obj):
        return "Approved" if obj.approved else "Pending"


class LeaveRequestWriteSerializer(serializers.ModelSerializer):
    """
    Students submit this. 'student' and 'approved' are never accepted from input —
    both are set by the view from the auth token and business logic respectively.
    """
    class Meta:
        model  = LeaveRequest
        fields = ['id', 'from_date', 'to_date', 'reason', 'approved']
        read_only_fields = ['id', 'approved']

    def validate_from_date(self, value):
        if value < timezone.now().date():
            raise serializers.ValidationError(
                "Leave cannot be requested for a past date."
            )
        return value

    def validate(self, attrs):
        from_date = attrs.get(
            'from_date',
            getattr(self.instance, 'from_date', None)
        )
        to_date = attrs.get(
            'to_date',
            getattr(self.instance, 'to_date', None)
        )
        if from_date and to_date and to_date < from_date:
            raise serializers.ValidationError({
                'to_date': "End date cannot be before start date."
            })
        return attrs

    def to_representation(self, instance):
        return LeaveRequestReadSerializer(instance, context=self.context).data


# ===========================================================================
# ROUTINE  (model lives in academics — serializer here for student/teacher views)
# ===========================================================================

class RoutineSerializer(serializers.ModelSerializer):
    """
    Student-facing class schedule.
    Resolves subject name and day label — frontend never decodes integers.
    """
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    subject_code = serializers.CharField(source='subject.code', read_only=True)
    day          = serializers.CharField(
        source='get_day_of_week_display', read_only=True
    )

    class Meta:
        model  = Routine
        fields = [
            'id', 'subject_name', 'subject_code',
            'day', 'start_time', 'end_time', 'room', 'section',
        ]
        read_only_fields = fields


class TeacherRoutineSerializer(serializers.ModelSerializer):
    """
    Teacher-facing schedule — same shape but includes faculty context.
    """
    subject_name = serializers.CharField(source='subject.name',         read_only=True)
    subject_code = serializers.CharField(source='subject.code',         read_only=True)
    faculty_name = serializers.CharField(source='subject.faculty.name', read_only=True)
    day          = serializers.CharField(
        source='get_day_of_week_display', read_only=True
    )

    class Meta:
        model  = Routine
        fields = [
            'id', 'subject_name', 'subject_code', 'faculty_name',
            'day', 'start_time', 'end_time', 'room', 'section',
        ]
        read_only_fields = fields


# ===========================================================================
# RESULT  (model lives in academics)
# ===========================================================================

class ResultSerializer(serializers.ModelSerializer):
    """
    Student sees their own results.
    Only published results should ever reach this serializer — filter in the view.
    """
    subject_name  = serializers.CharField(
        source='exam_routine.subject.name', read_only=True
    )
    subject_code  = serializers.CharField(
        source='exam_routine.subject.code', read_only=True
    )
    exam_type     = serializers.CharField(
        source='exam_routine.get_exam_type_display', read_only=True
    )
    exam_date     = serializers.DateField(
        source='exam_routine.exam_date', read_only=True
    )
    full_marks    = serializers.IntegerField(
        source='exam_routine.full_marks', read_only=True
    )
    grade_display = serializers.CharField(
        source='get_grade_display', read_only=True
    )

    class Meta:
        model  = Result
        fields = [
            'id',
            'subject_name', 'subject_code',
            'exam_type', 'exam_date',
            'marks_obtained', 'full_marks',
            'grade', 'grade_display',
            'is_absent', 'remarks',
        ]
        read_only_fields = fields


# ===========================================================================
# ATTENDANCE  (model lives in attendance app)
# ===========================================================================

class MarkAttendanceSerializer(serializers.ModelSerializer):
    """
    Teacher posts this. 'marked_by' is excluded — set from auth token in view.
    """
    class Meta:
        model  = Attendance
        fields = ['id', 'student', 'subject', 'date', 'status']
        read_only_fields = ['id']

    def validate_date(self, value):
        if value > timezone.now().date():
            raise serializers.ValidationError(
                "Cannot mark attendance for a future date."
            )
        return value


# ===========================================================================
# NOTICE  (model lives in notices app)
# ===========================================================================

class NoticeSerializer(serializers.ModelSerializer):
    """
    Read-only notice card for students and teachers.
    """
    type_display = serializers.CharField(
        source='get_type_display', read_only=True
    )

    class Meta:
        model  = Notice
        fields = ['id', 'title', 'type', 'type_display', 'content']
        read_only_fields = fields


# ===========================================================================
# FEEDBACK  (model lives in feedback app)
# ===========================================================================

class TeacherFeedbackSerializer(serializers.ModelSerializer):
    """
    Teacher reads feedback submitted about them.
    target_teacher is FK to User — no .user traversal needed.
    """
    student_name = serializers.SerializerMethodField()
    student_roll = serializers.CharField(
        source='student.roll_no', read_only=True
    )
    type_display = serializers.CharField(
        source='get_type_display', read_only=True
    )

    class Meta:
        model  = Feedback
        fields = [
            'id', 'student_name', 'student_roll',
            'type', 'type_display', 'message', 'submitted_at',
        ]
        read_only_fields = fields

    def get_student_name(self, obj):
        return f"{obj.student.user.first_name} {obj.student.user.last_name}".strip()