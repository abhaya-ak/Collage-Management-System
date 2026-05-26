# subjects/serializers.py
from rest_framework import serializers
from .models import Subject
from .services import SubjectService

class SubjectReadSerializer(serializers.ModelSerializer):
    teacher_name = serializers.SerializerMethodField()
    faculty_name = serializers.CharField(source='faculty.name', read_only=True)
    total         = serializers.SerializerMethodField()

    class Meta:
        model  = Subject
        fields = [
            'id',
            'code',
            'name',
            'faculty',       # raw ID — useful for edit forms to pre-select
            'faculty_name',  # human label — useful for display
            'teacher',       # raw ID
            'teacher_name',  # human label
            'full_marks',
            'pass_marks',
            'total',         # computed: full_marks (sanity check field for UI)
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields  # this serializer is NEVER used for writes

    def get_teacher_name(self, obj):
        if obj.teacher and obj.teacher.user:
            return f"{obj.teacher.user.first_name} {obj.teacher.user.last_name}".strip()
        return None  # null is cleaner than "Unassigned" — let the frontend decide

    def get_total(self, obj):
        # Exposed so UI can show "40 / 100" without doing math client-side
        return obj.full_marks

class SubjectWriteSerializer(serializers.ModelSerializer):

#    What the frontend sends.
    class Meta:
        model  = Subject
        fields = [
            'id',
            'code',
            'name',
            'faculty',
            'teacher',
            'full_marks',
            'pass_marks',
        ]
        read_only_fields = ['id']

    def validate_code(self, value):
        try:
            return SubjectService.validate_code_unique(
                value, exclude_pk=self.instance.pk if self.instance else None
            )
        except ValueError as e:
            raise serializers.ValidationError(str(e))

    def validate_pass_marks(self, value):
        try:
            SubjectService.validate_pass_marks(value)
        except ValueError as e:
            raise serializers.ValidationError(str(e))
        return value

    def validate(self, attrs):
        full_marks = attrs.get('full_marks', getattr(self.instance, 'full_marks', None))
        pass_marks = attrs.get('pass_marks', getattr(self.instance, 'pass_marks', None))
        try:
            SubjectService.validate_marks_range(full_marks, pass_marks)
        except ValueError as e:
            raise serializers.ValidationError({'pass_marks': str(e)})
        return attrs

    def to_representation(self, instance):
        """
        After a successful write, return the full read representation.
        Avoids a second API call from the frontend just to see what was saved.
        """
        return SubjectReadSerializer(instance, context=self.context).data