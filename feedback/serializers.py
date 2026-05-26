# feedback/serializers.py
from rest_framework import serializers

from .models import Feedback
from students.models import Teacher
from .services import FeedbackService


# ─────────────────────────────────────────────────────────────────────────────
# Write — student submits feedback
# ─────────────────────────────────────────────────────────────────────────────

class FeedbackWriteSerializer(serializers.ModelSerializer):
    """
    Student submits this.
    'student' excluded — injected from auth token in the view.
    'status' / reply fields excluded — those are admin-only.
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

# Read — student sees their own submissions
class FeedbackStudentReadSerializer(serializers.ModelSerializer):
    """
    Student view: their own feedback + current status + admin reply if present.
    No student fields (they know who they are).
    """
    type_display    = serializers.CharField(source='get_type_display',   read_only=True)
    status_display  = serializers.CharField(source='get_status_display', read_only=True)
    directed_at     = serializers.SerializerMethodField()

    class Meta:
        model  = Feedback
        fields = [
            'id',
            'type', 'type_display',
            'message',
            'directed_at',
            'status', 'status_display',
            'admin_reply',
            'replied_at',
            'submitted_at',
        ]
        read_only_fields = fields

    def get_directed_at(self, obj):
        return FeedbackService.resolve_directed_at(obj)


# ─────────────────────────────────────────────────────────────────────────────
# Read — teacher sees what was submitted about them
# ─────────────────────────────────────────────────────────────────────────────

class FeedbackTeacherReadSerializer(serializers.ModelSerializer):
    """
    Teacher sees who submitted what about them.
    Hides email — roll number is sufficient identification.
    """
    type_display = serializers.CharField(source='get_type_display', read_only=True)
    student_name = serializers.SerializerMethodField()
    student_roll = serializers.CharField(source='student.roll_no', read_only=True)

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


# ─────────────────────────────────────────────────────────────────────────────
# Read — admin sees full picture
# ─────────────────────────────────────────────────────────────────────────────

class FeedbackAdminReadSerializer(serializers.ModelSerializer):
    """Full record for admin dashboard — all fields including status lifecycle."""
    type_display    = serializers.CharField(source='get_type_display',   read_only=True)
    status_display  = serializers.CharField(source='get_status_display', read_only=True)
    student_name    = serializers.SerializerMethodField()
    student_roll    = serializers.CharField(source='student.roll_no', read_only=True)
    teacher_name    = serializers.SerializerMethodField()
    directed_at     = serializers.SerializerMethodField()
    replied_by_name = serializers.SerializerMethodField()

    class Meta:
        model  = Feedback
        fields = [
            'id',
            'student_name', 'student_roll',
            'type', 'type_display',
            'message',
            'target_teacher', 'teacher_name',
            'directed_at',
            'status', 'status_display',
            'admin_reply',
            'replied_at',
            'replied_by', 'replied_by_name',
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

    def get_replied_by_name(self, obj):
        return FeedbackService.resolve_teacher_name(obj.replied_by)


# ─────────────────────────────────────────────────────────────────────────────
# Write — admin replies to a feedback item
# ─────────────────────────────────────────────────────────────────────────────

class FeedbackReplySerializer(serializers.Serializer):
    """
    Admin sets status and optionally provides a reply message.

    Rules (enforced by FeedbackService.validate_reply_content):
      - RESOLVED / CLOSED → admin_reply is required.
      - PENDING / REVIEWED → admin_reply is optional.

    Returns the full FeedbackAdminReadSerializer representation on success.
    """
    status      = serializers.ChoiceField(choices=Feedback.Status.choices)
    admin_reply = serializers.CharField(required=False, default='', allow_blank=True)

    def validate(self, attrs):
        try:
            FeedbackService.validate_reply_content(
                attrs.get('admin_reply', ''),
                attrs['status'],
            )
        except ValueError as e:
            raise serializers.ValidationError({'admin_reply': str(e)})
        return attrs

    def to_representation(self, instance):
        return FeedbackAdminReadSerializer(instance, context=self.context).data