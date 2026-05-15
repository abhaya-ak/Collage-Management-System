'''from rest_framework import serializers
from .models import Attendance

class AttendanceWriteSerializer(serializers.ModelSerializer):
    """
    Contract for POST /api/v1/attendance/mark/
    Accepts exact JSON: {"student": 5, "subject": 1, "date": "2026-04-29", "status": "Present"}
    """
    class Meta:
        model = Attendance
        # 'marked_by' is explicitly excluded. We trust the token, not the JSON payload.
        fields = ['student', 'subject', 'date', 'status']

class AttendanceReadSerializer(serializers.ModelSerializer):
    """
    Contract for GET /api/v1/attendance/student/{id}/
    Returns a rich report for the UI.
    """
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    teacher_name = serializers.SerializerMethodField()

    class Meta:
        model = Attendance
        fields = ['id', 'subject_name', 'date', 'status', 'teacher_name']

    def get_teacher_name(self, obj):
        if obj.marked_by:
            return f"{obj.marked_by.user.first_name} {obj.marked_by.user.last_name}"
        return "Unknown"'''