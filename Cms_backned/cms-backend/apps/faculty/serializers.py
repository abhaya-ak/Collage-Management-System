"""Serializers for the faculty domain."""

from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from apps.academics.models import AcademicYear, Program, Section, Semester, Subject
from apps.core.enums import FacultyStatus
from apps.faculty.models import Faculty, FacultyAssignment


# --- reads ------------------------------------------------------------------
class FacultyAssignmentSerializer(serializers.ModelSerializer):
    academic_year = serializers.CharField(source="academic_year.name", read_only=True)
    program = serializers.CharField(source="program.code", read_only=True)
    semester = serializers.IntegerField(source="semester.number", read_only=True)
    section = serializers.CharField(source="section.name", read_only=True)
    subject = serializers.CharField(source="subject.code", read_only=True)

    class Meta:
        model = FacultyAssignment
        fields = ["id", "academic_year", "program", "semester", "section",
                  "subject", "created_at"]


class FacultySerializer(serializers.ModelSerializer):
    account_email = serializers.EmailField(source="user.email", read_only=True)
    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = Faculty
        fields = ["id", "employee_id", "account_email", "full_name",
                  "designation", "join_date", "status", "created_at"]
        read_only_fields = fields


class FacultyDetailSerializer(FacultySerializer):
    assignments = FacultyAssignmentSerializer(many=True, read_only=True)

    class Meta(FacultySerializer.Meta):
        fields = FacultySerializer.Meta.fields + ["assignments"]


# --- writes -----------------------------------------------------------------
class FacultyCreateSerializer(serializers.Serializer):
    """POST /faculty/ — creates account + faculty profile. employee_id is generated."""

    account_email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    designation = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    join_date = serializers.DateField()
    status = serializers.ChoiceField(choices=FacultyStatus.choices, required=False, default=FacultyStatus.ACTIVE)

    def validate_password(self, value):
        validate_password(value)
        return value


class FacultyUpdateSerializer(serializers.ModelSerializer):
    """PATCH — profile fields only (no account/employee_id changes)."""

    class Meta:
        model = Faculty
        fields = ["designation", "join_date", "status"]


class AssignSubjectSerializer(serializers.Serializer):
    academic_year = serializers.PrimaryKeyRelatedField(queryset=AcademicYear.objects.all())
    program = serializers.PrimaryKeyRelatedField(queryset=Program.objects.all())
    semester = serializers.PrimaryKeyRelatedField(queryset=Semester.objects.all())
    section = serializers.PrimaryKeyRelatedField(queryset=Section.objects.all())
    subject = serializers.PrimaryKeyRelatedField(queryset=Subject.objects.all())


class UpdateAssignmentSerializer(AssignSubjectSerializer):
    assignment = serializers.PrimaryKeyRelatedField(queryset=FacultyAssignment.objects.all())


class RemoveAssignmentSerializer(serializers.Serializer):
    assignment = serializers.PrimaryKeyRelatedField(queryset=FacultyAssignment.objects.all())
