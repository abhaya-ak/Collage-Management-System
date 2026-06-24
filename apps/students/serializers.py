"""Serializers for the students domain."""

from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from apps.academics.models import AcademicYear, Program, Routine, Section, Semester
from apps.attendance.models import AttendanceRecord
from apps.core.enums import Gender
from apps.faculty.models import FacultyAssignment, FacultyLeave
from apps.students.models import Student, StudentDocument, StudentEnrollment

_BASE_READ_ONLY = ["id", "created_at", "updated_at"]


# --- reads ------------------------------------------------------------------
class EnrollmentReadSerializer(serializers.ModelSerializer):
    academic_year = serializers.CharField(source="academic_year.name", read_only=True)
    program = serializers.CharField(source="program.code", read_only=True)
    semester = serializers.IntegerField(source="semester.number", read_only=True)
    section = serializers.CharField(source="section.name", read_only=True)

    class Meta:
        model = StudentEnrollment
        fields = ["id", "academic_year", "program", "semester", "section",
                  "status", "enrollment_date"]


class StudentDocumentSerializer(serializers.ModelSerializer):
    class Meta:
        model = StudentDocument
        fields = ["id", "document_type", "file", "uploaded_at"]
        read_only_fields = ["id", "uploaded_at"]


class StudentSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    account_email = serializers.EmailField(source="user.email", read_only=True)
    active_enrollment = serializers.SerializerMethodField()

    class Meta:
        model = Student
        fields = [
            "id", "student_id", "registration_number", "account_email",
            "first_name", "middle_name", "last_name", "full_name",
            "gender", "date_of_birth", "email", "phone", "address",
            "admission_date", "profile_photo", "status",
            "active_enrollment", "created_at",
        ]
        read_only_fields = fields  # this serializer is read-only

    def get_active_enrollment(self, obj):
        # Uses prefetched enrollments — no extra query.
        active = next((e for e in obj.enrollments.all() if e.status == "ACTIVE"), None)
        return EnrollmentReadSerializer(active).data if active else None


class StudentDetailSerializer(StudentSerializer):
    enrollments = EnrollmentReadSerializer(many=True, read_only=True)
    documents = StudentDocumentSerializer(many=True, read_only=True)

    class Meta(StudentSerializer.Meta):
        fields = StudentSerializer.Meta.fields + ["enrollments", "documents"]


# --- writes -----------------------------------------------------------------
class StudentUpdateSerializer(serializers.ModelSerializer):
    """PATCH — profile fields only. Cannot change identity/account/academic state."""

    class Meta:
        model = Student
        fields = ["first_name", "middle_name", "last_name", "gender",
                  "date_of_birth", "email", "phone", "address",
                  "profile_photo", "status"]


class _EnrollmentInputSerializer(serializers.Serializer):
    """Shared input for enroll / promote."""

    academic_year = serializers.PrimaryKeyRelatedField(queryset=AcademicYear.objects.all())
    program = serializers.PrimaryKeyRelatedField(queryset=Program.objects.all())
    semester = serializers.PrimaryKeyRelatedField(queryset=Semester.objects.all())
    section = serializers.PrimaryKeyRelatedField(queryset=Section.objects.all())
    enrollment_date = serializers.DateField()

    def validate(self, attrs):
        section = attrs["section"]
        if (section.program_id != attrs["program"].id
                or section.semester_id != attrs["semester"].id):
            raise serializers.ValidationError(
                {"section": "Section does not belong to the selected program/semester."}
            )
        return attrs


class EnrollSerializer(_EnrollmentInputSerializer):
    pass


class PromoteSerializer(_EnrollmentInputSerializer):
    pass


class ChangeSectionSerializer(serializers.Serializer):
    section = serializers.PrimaryKeyRelatedField(queryset=Section.objects.all())


class AdmissionSerializer(serializers.Serializer):
    """
    Input for POST /students/admission/ — account + profile + program.

    academic_year, semester, and section are NO LONGER required from the caller.
    The service layer auto-resolves them:
        academic_year → current AcademicYear (is_current=True)
        semester      → Semester 1 (number=1)
        section       → first alphabetical section with available capacity

    account_email (login) and password are also NOT accepted — both are generated
    automatically and returned in the response (the temp password once).
    """

    # account — login email + temporary password are system-generated

    # profile
    first_name = serializers.CharField(max_length=100)
    middle_name = serializers.CharField(max_length=100, required=False, allow_blank=True, default="")
    last_name = serializers.CharField(max_length=100)
    gender = serializers.ChoiceField(choices=Gender.choices)
    date_of_birth = serializers.DateField()
    email = serializers.EmailField()
    phone = serializers.CharField(max_length=20, required=False, allow_blank=True, default="")
    address = serializers.CharField(required=False, allow_blank=True, default="")
    admission_date = serializers.DateField()
    registration_number = serializers.CharField(max_length=50)

    # enrollment — admin picks program; system resolves the rest
    program = serializers.PrimaryKeyRelatedField(queryset=Program.objects.all())
    enrollment_date = serializers.DateField()



# --- student self-service reads ---------------------------------------------
class MyAttendanceSerializer(serializers.ModelSerializer):
    date = serializers.DateField(source="session.attendance_date", read_only=True)
    subject = serializers.CharField(source="session.faculty_assignment.subject.code", read_only=True)

    class Meta:
        model = AttendanceRecord
        fields = ["id", "date", "subject", "status"]


class MyRoutineSerializer(serializers.ModelSerializer):
    subject = serializers.CharField(source="faculty_assignment.subject.code", read_only=True)
    teacher = serializers.CharField(source="faculty_assignment.faculty.employee_id", read_only=True)

    class Meta:
        model = Routine
        fields = ["id", "day_of_week", "start_time", "end_time", "subject", "teacher"]


class MyTeacherSerializer(serializers.ModelSerializer):
    subject = serializers.CharField(source="subject.code", read_only=True)
    teacher_id = serializers.CharField(source="faculty.employee_id", read_only=True)
    teacher_name = serializers.CharField(source="faculty.full_name", read_only=True)

    class Meta:
        model = FacultyAssignment
        fields = ["id", "subject", "teacher_id", "teacher_name"]


class MyTeacherLeaveSerializer(serializers.ModelSerializer):
    teacher_id = serializers.CharField(source="faculty.employee_id", read_only=True)
    teacher_name = serializers.CharField(source="faculty.full_name", read_only=True)

    class Meta:
        model = FacultyLeave
        fields = ["id", "teacher_id", "teacher_name", "start_date", "end_date", "status", "reason"]
