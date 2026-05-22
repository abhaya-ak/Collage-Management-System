# feedback/serializers.py
from rest_framework import serializers

from .models import Feedback
from students.models import Teacher
from .services import FeedbackService


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

    def validate_message(self, value):
        try:
            return FeedbackService.validate_message(value)
        except ValueError as e:
            raise serializers.ValidationError(str(e))

    def validate_target_teacher(self, user):
        try:
            FeedbackService.validate_target_teacher(user)
        except ValueError as e:
            raise serializers.ValidationError(str(e))
        return user

    def to_representation(self, instance):
        return FeedbackStudentReadSerializer(instance, context=self.context).data

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
        return FeedbackService.resolve_directed_at(obj)


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
        return FeedbackService.resolve_teacher_name(obj.target_teacher)

    def get_directed_at(self, obj):
        return FeedbackService.resolve_directed_at(obj)