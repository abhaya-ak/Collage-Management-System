from rest_framework import serializers
from .models import Subject

class SubjectWriteSerializer(serializers.ModelSerializer):
    """
    Contract for POST / PUT / PATCH
    Accepts: {"name": "Physics", "course": "BSc", "teacher": 2}
    """
    class Meta:
        model = Subject
        fields = ['id', 'name', 'course', 'teacher']

class SubjectReadSerializer(serializers.ModelSerializer):
    """
    Contract for GET (List and Detail)
    Returns: {"id": 1, "name": "Physics", "course": "BSc", "teacher_name": "Prof. Alan Turing"}
    """
    teacher_name = serializers.SerializerMethodField()

    class Meta:
        model = Subject
        fields = ['id', 'name', 'course', 'teacher_name']

    def get_teacher_name(self, obj):
        # Gracefully handle the case where a subject currently has no teacher assigned
        if obj.teacher:
            return f"Prof. {obj.teacher.user.first_name} {obj.teacher.user.last_name}"
        return "Unassigned"