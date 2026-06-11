"""Serializers for academics entities."""

from rest_framework import serializers

from apps.academics.models import (
    AcademicYear,
    Program,
    ProgramSemesterSubject,
    Section,
    Semester,
    Subject,
)

_BASE_READ_ONLY = ["id", "created_at", "updated_at"]


class AcademicYearSerializer(serializers.ModelSerializer):
    # Declared explicitly so DRF does NOT auto-attach a UniqueValidator from the
    # partial UniqueConstraint (which ignores the condition). The single-current
    # rule is enforced by the DB constraint + the service layer.
    is_current = serializers.BooleanField(required=False, default=False)

    class Meta:
        model = AcademicYear
        fields = ["id", "name", "start_date", "end_date", "is_current",
                  "created_at", "updated_at"]
        read_only_fields = _BASE_READ_ONLY

    def validate(self, attrs):
        start = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if start and end and end <= start:
            raise serializers.ValidationError(
                {"end_date": "End date must be after start date."}
            )
        return attrs


class ProgramSerializer(serializers.ModelSerializer):
    class Meta:
        model = Program
        fields = ["id", "code", "name", "duration_years", "total_semesters",
                  "description", "created_at", "updated_at"]
        read_only_fields = _BASE_READ_ONLY


class SemesterSerializer(serializers.ModelSerializer):
    class Meta:
        model = Semester
        fields = ["id", "number", "name", "created_at", "updated_at"]
        read_only_fields = _BASE_READ_ONLY


class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = ["id", "code", "name", "credit_hours", "theory_hours",
                  "practical_hours", "created_at", "updated_at"]
        read_only_fields = _BASE_READ_ONLY


class SectionSerializer(serializers.ModelSerializer):
    program_code = serializers.CharField(source="program.code", read_only=True)
    semester_number = serializers.IntegerField(source="semester.number", read_only=True)

    class Meta:
        model = Section
        fields = ["id", "program", "program_code", "semester", "semester_number",
                  "name", "capacity", "created_at", "updated_at"]
        read_only_fields = _BASE_READ_ONLY


class ProgramSemesterSubjectSerializer(serializers.ModelSerializer):
    program_code = serializers.CharField(source="program.code", read_only=True)
    semester_number = serializers.IntegerField(source="semester.number", read_only=True)
    subject_code = serializers.CharField(source="subject.code", read_only=True)

    class Meta:
        model = ProgramSemesterSubject
        fields = ["id", "program", "program_code", "semester", "semester_number",
                  "subject", "subject_code", "is_elective", "created_at", "updated_at"]
        read_only_fields = _BASE_READ_ONLY
