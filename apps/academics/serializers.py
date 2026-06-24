"""Serializers for academics entities."""

from rest_framework import serializers

from apps.academics.models import (
    AcademicLeave,
    AcademicYear,
    Program,
    ProgramSemesterSubject,
    Routine,
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


class RoutineSerializer(serializers.ModelSerializer):
    subject = serializers.CharField(source="faculty_assignment.subject.code", read_only=True)
    teacher = serializers.CharField(source="faculty_assignment.faculty.employee_id", read_only=True)
    section = serializers.CharField(source="faculty_assignment.section.name", read_only=True)

    class Meta:
        model = Routine
        fields = ["id", "faculty_assignment", "day_of_week", "start_time", "end_time",
                  "subject", "teacher", "section", "created_at"]
        read_only_fields = ["id", "subject", "teacher", "section", "created_at"]


class AcademicLeaveSerializer(serializers.ModelSerializer):
    class Meta:
        model = AcademicLeave
        fields = ["id", "title", "start_date", "end_date", "description",
                  "academic_year", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate(self, attrs):
        start = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if start and end and end < start:
            raise serializers.ValidationError({"end_date": "End date cannot be before start date."})
        return attrs


# ---------------------------------------------------------------------------
# Phase 2 — Section Recommendation
# ---------------------------------------------------------------------------
class SectionRecommendationSerializer(serializers.Serializer):
    """Output for GET /api/students/recommend-section/"""
    section_id   = serializers.UUIDField(source="section.id")
    section_name = serializers.CharField(source="section.name")
    occupancy    = serializers.IntegerField()
    capacity     = serializers.IntegerField()
    is_unlimited = serializers.SerializerMethodField()
    fill_pct     = serializers.SerializerMethodField()

    def get_is_unlimited(self, obj):
        return obj["capacity"] == 0

    def get_fill_pct(self, obj):
        if obj["capacity"] == 0:
            return 0.0
        return round(obj["occupancy"] / obj["capacity"] * 100, 1)


# ---------------------------------------------------------------------------
# Phase 3 — Bulk Promotion
# ---------------------------------------------------------------------------
class BulkPromoteSerializer(serializers.Serializer):
    """Input for POST /api/students/bulk-promote/"""
    academic_year = serializers.PrimaryKeyRelatedField(
        queryset=AcademicYear.objects.all()
    )
    program      = serializers.PrimaryKeyRelatedField(
        queryset=Program.objects.all()
    )
    from_semester = serializers.PrimaryKeyRelatedField(
        queryset=Semester.objects.all()
    )
    to_semester   = serializers.PrimaryKeyRelatedField(
        queryset=Semester.objects.all()
    )

    def validate(self, attrs):
        if attrs["from_semester"].number >= attrs["to_semester"].number:
            raise serializers.ValidationError(
                {"to_semester": "Target semester must be higher than the source semester."}
            )
        return attrs


# ---------------------------------------------------------------------------
# Phase 4 — Capacity Dashboard
# ---------------------------------------------------------------------------
class SectionCapacitySerializer(serializers.ModelSerializer):
    """Output for GET /api/academics/sections/capacity/"""
    program      = serializers.CharField(source="program.code")
    semester     = serializers.IntegerField(source="semester.number")
    active_count = serializers.IntegerField(read_only=True)   # annotated
    fill_pct     = serializers.FloatField(read_only=True)     # annotated
    status       = serializers.SerializerMethodField()

    class Meta:
        model = Section
        fields = ["id", "program", "semester", "name", "capacity",
                  "active_count", "fill_pct", "status"]

    def get_status(self, obj):
        if obj.capacity == 0:
            return "UNLIMITED"
        if obj.active_count >= obj.capacity:
            return "FULL"
        if obj.active_count >= obj.capacity * 0.9:
            return "ALMOST_FULL"
        return "AVAILABLE"

