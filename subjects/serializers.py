# subjects/serializers.py
from rest_framework import serializers
from .models import Subject


# ---------------------------------------------------------------------------
# Read Serializer — GET (list + detail)
# ---------------------------------------------------------------------------

class SubjectReadSerializer(serializers.ModelSerializer):
    """
    What the frontend receives.
    FK fields resolved to human-readable strings — not raw IDs.
    """
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


# ---------------------------------------------------------------------------
# Write Serializer — POST / PUT / PATCH
# ---------------------------------------------------------------------------

class SubjectWriteSerializer(serializers.ModelSerializer):
    """
    What the frontend sends.
    Accepts FK IDs. Validates marks logic. Returns minimal confirmation.
    """

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

    # --- Field-level validation -------------------------------------------

    def validate_code(self, value):
        """
        Code must be unique across all subjects.
        On UPDATE, exclude the current instance from the uniqueness check.
        """
        qs = Subject.objects.filter(code__iexact=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                f"A subject with code '{value}' already exists."
            )
        return value.upper()  # normalize: always store as uppercase e.g. CS201

    def validate_pass_marks(self, value):
        if value < 1:
            raise serializers.ValidationError("Pass marks must be at least 1.")
        return value

    # --- Object-level validation -------------------------------------------

    def validate(self, attrs):
        """
        Rules that require looking at multiple fields together.
        Works for both CREATE (no self.instance) and UPDATE (partial or full).
        """
        # Resolve final values: on PATCH, fall back to existing instance value
        full_marks = attrs.get(
            'full_marks',
            getattr(self.instance, 'full_marks', None)
        )
        pass_marks = attrs.get(
            'pass_marks',
            getattr(self.instance, 'pass_marks', None)
        )

        if full_marks is not None and pass_marks is not None:
            if pass_marks >= full_marks:
                raise serializers.ValidationError({
                    'pass_marks': (
                        f"Pass marks ({pass_marks}) must be "
                        f"strictly less than full marks ({full_marks})."
                    )
                })

        return attrs

    def to_representation(self, instance):
        """
        After a successful write, return the full read representation.
        Avoids a second API call from the frontend just to see what was saved.
        """
        return SubjectReadSerializer(instance, context=self.context).data