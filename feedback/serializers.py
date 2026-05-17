# feedback/serializers.py
from rest_framework import serializers

from .models import Feedback
from students.models import Teacher


# ===========================================================================
# HELPERS
# ===========================================================================

def _resolve_teacher_name(user):
    """
    target_teacher is FK → User directly (not → Teacher).
    So name comes from user.first_name, not user.user.first_name.
    """
    if not user:
        return None
    return f"{user.first_name} {user.last_name}".strip() or user.username


# ===========================================================================
# WRITE — student submits feedback
# ===========================================================================

class FeedbackWriteSerializer(serializers.ModelSerializer):
    """
    Student submits this.
    'student' excluded — set from auth token in view.
    'submitted_at' excluded — set by DB default.
    'target_teacher' optional — null means feedback is directed at the college.
    """

    class Meta:
        model  = Feedback
        fields = ['id', 'type', 'message', 'target_teacher']
        read_only_fields = ['id']

    # --- Field-level -------------------------------------------------------

    def validate_message(self, value):
        value = value.strip()
        if len(value) < 10:
            raise serializers.ValidationError(
                "Message is too short. Please provide at least 10 characters."
            )
        if len(value) > 2000:
            raise serializers.ValidationError(
                "Message cannot exceed 2000 characters."
            )
        return value

    def validate_target_teacher(self, user):
        """
        target_teacher must be an actual Teacher — not just any User.
        Prevents students from tagging admin accounts as 'teachers'.
        """
        if user is None:
            return None  # feedback directed at college — perfectly valid

        if not Teacher.objects.filter(user=user).exists():
            raise serializers.ValidationError(
                "The selected user is not a registered teacher."
            )
        return user

    def to_representation(self, instance):
        return FeedbackStudentReadSerializer(instance, context=self.context).data


# ===========================================================================
# READ — student views their own submissions
# ===========================================================================

class FeedbackStudentReadSerializer(serializers.ModelSerializer):
    """
    What a student sees when listing their own submitted feedback.
    No student fields (they know who they are).
    Teacher name resolved from the User FK directly.
    """
    type_display   = serializers.CharField(
        source='get_type_display', read_only=True
    )
    directed_at    = serializers.SerializerMethodField()
    submitted_at   = serializers.DateTimeField(read_only=True)

    class Meta:
        model  = Feedback
        fields = [
            'id',
            'type', 'type_display',
            'message',
            'directed_at',   # human label: teacher name or "College Administration"
            'submitted_at',
        ]
        read_only_fields = fields

    def get_directed_at(self, obj):
        if obj.target_teacher:
            return _resolve_teacher_name(obj.target_teacher)
        return "College Administration"


# ===========================================================================
# READ — teacher views feedback directed at them
# ===========================================================================

class FeedbackTeacherReadSerializer(serializers.ModelSerializer):
    """
    Teacher sees who submitted what about them.
    Hides the student's email — roll number is enough for identification.
    """
    type_display = serializers.CharField(
        source='get_type_display', read_only=True
    )
    student_name = serializers.SerializerMethodField()
    student_roll = serializers.CharField(
        source='student.roll_no', read_only=True
    )

    class Meta:
        model  = Feedback
        fields = [
            'id',
            'student_name', 'student_roll',
            'type', 'type_display',
            'message',
            'submitted_at',
        ]
        read_only_fields = fields

    def get_student_name(self, obj):
        u = obj.student.user
        return f"{u.first_name} {u.last_name}".strip()


# ===========================================================================
# READ — admin views all feedback
# ===========================================================================

class FeedbackAdminReadSerializer(serializers.ModelSerializer):
    """
    Full picture for admin dashboard.
    Shows student + teacher details, type, message, timestamp.
    """
    type_display   = serializers.CharField(
        source='get_type_display', read_only=True
    )
    student_name   = serializers.SerializerMethodField()
    student_roll   = serializers.CharField(
        source='student.roll_no', read_only=True
    )
    teacher_name   = serializers.SerializerMethodField()
    directed_at    = serializers.SerializerMethodField()

    class Meta:
        model  = Feedback
        fields = [
            'id',
            'student_name', 'student_roll',
            'type', 'type_display',
            'message',
            'target_teacher', 'teacher_name',
            'directed_at',
            'submitted_at',
        ]
        read_only_fields = fields

    def get_student_name(self, obj):
        u = obj.student.user
        return f"{u.first_name} {u.last_name}".strip()

    def get_teacher_name(self, obj):
        return _resolve_teacher_name(obj.target_teacher)

    def get_directed_at(self, obj):
        """
        Single clean label for display in admin table column.
        """
        if obj.target_teacher:
            return _resolve_teacher_name(obj.target_teacher)
        return "College Administration"