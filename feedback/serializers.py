from rest_framework import serializers
from .models import Feedback

class FeedbackWriteSerializer(serializers.ModelSerializer):
    """
    Contract for POST /api/v1/feedback/ (Used by Students)
    Accepts: {"target_teacher": 2, "subject": "Math Class", "message": "Too much homework!"}
    """
    class Meta:
        model = Feedback
        # Notice we exclude 'student' to prevent students from forging who sent it.
        fields = ['target_teacher', 'subject', 'message']

class FeedbackReadSerializer(serializers.ModelSerializer):
    """
    Contract for GET /api/v1/feedback/ (Used by Admins)
    Returns rich data for the admin dashboard table.
    """
    student_name = serializers.SerializerMethodField()
    student_roll_no = serializers.CharField(source='student.roll_no', read_only=True)
    teacher_name = serializers.SerializerMethodField()

    class Meta:
        model = Feedback
        fields = ['id', 'student_name', 'student_roll_no', 'teacher_name', 'subject', 'message', 'submitted_at']

    def get_student_name(self, obj):
        return f"{obj.student.user.first_name} {obj.student.user.last_name}"

    def get_teacher_name(self, obj):
        if obj.target_teacher:
            return f"{obj.target_teacher.user.first_name} {obj.target_teacher.user.last_name}"
        return "General Admin"