"""Serializers for the attendance domain."""

from rest_framework import serializers

from apps.attendance.models import AttendanceRecord, AttendanceSession
from apps.core.enums import AttendanceStatus
from apps.faculty.models import FacultyAssignment
from apps.students.models import Student


# --- reads ------------------------------------------------------------------
class AttendanceRecordSerializer(serializers.ModelSerializer):
    student_id = serializers.CharField(source="student.student_id", read_only=True)
    student_name = serializers.CharField(source="student.full_name", read_only=True)

    class Meta:
        model = AttendanceRecord
        fields = ["id", "student", "student_id", "student_name", "status"]


class AttendanceSessionSerializer(serializers.ModelSerializer):
    subject = serializers.CharField(source="faculty_assignment.subject.code", read_only=True)
    program = serializers.CharField(source="faculty_assignment.program.code", read_only=True)
    semester = serializers.IntegerField(source="faculty_assignment.semester.number", read_only=True)
    section = serializers.CharField(source="faculty_assignment.section.name", read_only=True)
    teacher = serializers.CharField(source="faculty_assignment.faculty.employee_id", read_only=True)

    class Meta:
        model = AttendanceSession
        fields = ["id", "faculty_assignment", "subject", "program", "semester",
                  "section", "teacher", "attendance_date", "remarks", "is_locked",
                  "created_at"]
        read_only_fields = fields


class AttendanceSessionDetailSerializer(AttendanceSessionSerializer):
    records = AttendanceRecordSerializer(many=True, read_only=True)

    class Meta(AttendanceSessionSerializer.Meta):
        fields = AttendanceSessionSerializer.Meta.fields + ["records"]


# --- writes -----------------------------------------------------------------
class CreateSessionSerializer(serializers.Serializer):
    faculty_assignment = serializers.PrimaryKeyRelatedField(
        queryset=FacultyAssignment.objects.all()
    )
    attendance_date = serializers.DateField()
    remarks = serializers.CharField(required=False, allow_blank=True, default="")


class _RecordInputSerializer(serializers.Serializer):
    student = serializers.PrimaryKeyRelatedField(queryset=Student.objects.all())
    status = serializers.ChoiceField(choices=AttendanceStatus.choices)


class MarkAttendanceSerializer(serializers.Serializer):
    records = _RecordInputSerializer(many=True, allow_empty=False)

    def validate_records(self, value):
        seen = set()
        for row in value:
            sid = row["student"].pk
            if sid in seen:
                raise serializers.ValidationError("Duplicate student in records.")
            seen.add(sid)
        return value
