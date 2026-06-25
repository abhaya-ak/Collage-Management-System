"""
Students API — thin viewset.

    POST   /api/students/admission/      admit_student (account + profile + enrollment)
    GET    /api/students/                list
    GET    /api/students/{id}/           retrieve (profile + history + documents)
    PATCH  /api/students/{id}/           update profile
    POST   /api/students/{id}/promote/   promote (old ACTIVE -> PROMOTED, new ACTIVE)
    POST   /api/students/{id}/enroll/    enroll (first/active enrollment)
    POST   /api/students/{id}/change-section/
"""

from django.db.models import Q
from rest_framework.decorators import action
from rest_framework.exceptions import MethodNotAllowed

from apps.academics.models import AcademicLeave, Routine
from apps.academics.serializers import AcademicLeaveSerializer
from apps.attendance.models import AttendanceRecord
from apps.faculty.models import FacultyAssignment, FacultyLeave
from apps.fees.models import StudentFee
from apps.fees.serializers import StudentFeeSerializer
from apps.students import selectors, serializers, services
from apps.students.models import Student
from apps.students.permissions import STUDENT_PERMISSIONS
from shared.responses import error_response, success_response
from shared.viewsets import BaseRBACViewSet


class StudentViewSet(BaseRBACViewSet):
    permission_map = STUDENT_PERMISSIONS
    # PUT and DELETE intentionally disabled; admission replaces plain create.
    http_method_names = ["get", "post", "patch", "head", "options"]

    search_fields = ["student_id", "registration_number", "first_name", "last_name", "email"]
    ordering_fields = ["student_id", "admission_date", "created_at"]
    filterset_fields = ["status", "gender"]

    def get_queryset(self):
        if self.action == "retrieve":
            return selectors.student_detail_qs()
        return selectors.student_list()

    def get_serializer_class(self):
        if self.action in ("update", "partial_update"):
            return serializers.StudentUpdateSerializer
        if self.action == "retrieve":
            return serializers.StudentDetailSerializer
        return serializers.StudentSerializer

    def create(self, request, *args, **kwargs):
        raise MethodNotAllowed("POST", detail="Use POST /api/students/admission/ instead.")

    # --- custom actions -----------------------------------------------------
    @action(detail=False, methods=["post"], url_path="admission")
    def admission(self, request):
        ser = serializers.AdmissionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        v = ser.validated_data
        profile_keys = ["first_name", "middle_name", "last_name", "gender",
                        "date_of_birth", "email", "phone", "address", "admission_date"]

        student = services.admit_student(
            registration_number=v["registration_number"],
            profile={k: v[k] for k in profile_keys},
            program=v["program"],
            actor=request.user,
        )
        temporary_password = student.temporary_password  # transient, set by service
        data = serializers.StudentDetailSerializer(
            selectors.get_student_profile(student.pk)
        ).data
        # Surface generated credentials once (admin relays to the student).
        data["temporary_password"] = temporary_password
        return success_response(data, "Student admitted successfully.", 201)

    @action(detail=True, methods=["post"], url_path="resend-credentials")
    def resend_credentials(self, request, pk=None):
        student = self.get_object()
        student = services.resend_credentials(student, actor=request.user)
        return success_response(
            {
                "student_id": student.student_id,
                "account_email": student.user.email,
                "temporary_password": student.temporary_password,
            },
            "Credentials resent successfully.",
        )

    @action(detail=True, methods=["post"])
    def promote(self, request, pk=None):
        student = self.get_object()
        ser = serializers.PromoteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        enrollment = services.promote_student(student, actor=request.user, **ser.validated_data)
        return success_response(
            serializers.EnrollmentReadSerializer(enrollment).data,
            "Student promoted successfully.", 201,
        )

    @action(detail=True, methods=["post"])
    def enroll(self, request, pk=None):
        student = self.get_object()
        ser = serializers.EnrollSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        enrollment = services.enroll_student(student, actor=request.user, **ser.validated_data)
        return success_response(
            serializers.EnrollmentReadSerializer(enrollment).data,
            "Student enrolled successfully.", 201,
        )

    @action(detail=True, methods=["post"], url_path="change-section")
    def change_section(self, request, pk=None):
        student = self.get_object()
        ser = serializers.ChangeSectionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        enrollment = services.change_section(student, ser.validated_data["section"], actor=request.user)
        return success_response(
            serializers.EnrollmentReadSerializer(enrollment).data,
            "Section changed successfully.",
        )

    # --- Phase 2: Section Recommendation ------------------------------------
    @action(detail=False, methods=["get"], url_path="recommend-section")
    def recommend_section(self, request):
        """
        GET /api/students/recommend-section/?program=<uuid>&semester=<uuid>

        Returns the recommended section (first available alphabetically) with
        current occupancy. Used as a UI hint on the Promote / Enroll forms.
        No row lock — advisory only.
        """
        from apps.academics.models import Program, Semester
        from apps.academics.serializers import SectionRecommendationSerializer

        program_id = request.query_params.get("program")
        semester_id = request.query_params.get("semester")

        if not program_id or not semester_id:
            return error_response("Both 'program' and 'semester' query params are required.", 400)

        program = Program.objects.filter(pk=program_id).first()
        semester = Semester.objects.filter(pk=semester_id).first()

        if not program:
            return error_response("Program not found.", 404)
        if not semester:
            return error_response("Semester not found.", 404)

        result = services.recommend_section(program=program, semester=semester)
        return success_response(
            SectionRecommendationSerializer(result).data,
            f"Recommended section: {result['section'].name}",
        )

    # --- Phase 3: Bulk Promotion --------------------------------------------
    @action(detail=False, methods=["post"], url_path="bulk-promote")
    def bulk_promote(self, request):
        """
        POST /api/students/bulk-promote/

        Promotes all ACTIVE students in (program, from_semester) to to_semester,
        auto-allocating sections. Returns a summary of promoted/failed counts.
        Individual failures do not abort the batch.
        """
        from apps.academics.serializers import BulkPromoteSerializer

        ser = BulkPromoteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        v = ser.validated_data

        result = services.bulk_promote_students(
            academic_year=v["academic_year"],
            program=v["program"],
            from_semester=v["from_semester"],
            to_semester=v["to_semester"],
            actor=request.user,
        )
        return success_response(result, (
            f"Bulk promotion complete: {result['promoted']} promoted, "
            f"{result['failed']} failed."
        ))

    # --- student self-service (the logged-in student's own data) ------------
    def _own_student(self, request):
        """The Student record for the logged-in user, or None."""
        return Student.objects.select_related("user").filter(user=request.user).first()

    def _own_section(self, student):
        active = selectors.get_active_enrollment(student)
        return active.section if active else None

    @action(detail=False, methods=["get"], url_path="me")
    def me(self, request):
        student = self._own_student(request)
        if student is None:
            return error_response("You do not have a student profile.", status_code=404)
        data = serializers.StudentDetailSerializer(
            selectors.get_student_profile(student.pk)
        ).data
        return success_response(data, "Your profile.")

    @action(detail=False, methods=["get"], url_path="me/attendance")
    def my_attendance(self, request):
        student = self._own_student(request)
        if student is None:
            return error_response("You do not have a student profile.", status_code=404)
        qs = (
            AttendanceRecord.objects.filter(student=student)
            .select_related("session__faculty_assignment__subject")
            .order_by("-session__attendance_date")
        )
        return success_response(
            serializers.MyAttendanceSerializer(qs, many=True).data, "Your attendance."
        )

    @action(detail=False, methods=["get"], url_path="me/routine")
    def my_routine(self, request):
        student = self._own_student(request)
        if student is None:
            return error_response("You do not have a student profile.", status_code=404)
        section = self._own_section(student)
        if section is None:
            return success_response([], "No active enrollment.")
        qs = Routine.objects.filter(
            faculty_assignment__section=section
        ).select_related("faculty_assignment__subject", "faculty_assignment__faculty")
        return success_response(
            serializers.MyRoutineSerializer(qs, many=True).data, "Your routine."
        )

    @action(detail=False, methods=["get"], url_path="me/teachers")
    def my_teachers(self, request):
        student = self._own_student(request)
        if student is None:
            return error_response("You do not have a student profile.", status_code=404)
        section = self._own_section(student)
        if section is None:
            return success_response([], "No active enrollment.")
        qs = FacultyAssignment.objects.filter(section=section).select_related(
            "subject", "faculty__user"
        )
        return success_response(
            serializers.MyTeacherSerializer(qs, many=True).data, "Your teachers."
        )

    @action(detail=False, methods=["get"], url_path="me/teacher-leaves")
    def my_teacher_leaves(self, request):
        student = self._own_student(request)
        if student is None:
            return error_response("You do not have a student profile.", status_code=404)
        section = self._own_section(student)
        if section is None:
            return success_response([], "No active enrollment.")
        faculty_ids = FacultyAssignment.objects.filter(
            section=section
        ).values_list("faculty_id", flat=True)
        qs = (
            FacultyLeave.objects.filter(faculty_id__in=faculty_ids, status="APPROVED")
            .select_related("faculty__user")
            .order_by("-start_date")
        )
        return success_response(
            serializers.MyTeacherLeaveSerializer(qs, many=True).data,
            "Approved leaves of your teachers.",
        )

    @action(detail=False, methods=["get"], url_path="me/academic-leaves")
    def my_academic_leaves(self, request):
        student = self._own_student(request)
        if student is None:
            return error_response("You do not have a student profile.", status_code=404)
        active = selectors.get_active_enrollment(student)
        ay_id = active.academic_year_id if active else None
        # Own academic year + global (academic_year IS NULL) holidays only.
        qs = AcademicLeave.objects.filter(
            Q(academic_year__isnull=True) | Q(academic_year_id=ay_id)
        ).order_by("-start_date")
        return success_response(
            AcademicLeaveSerializer(qs, many=True).data, "Your academic leaves."
        )

    @action(detail=False, methods=["get"], url_path="me/fees")
    def my_fees(self, request):
        student = self._own_student(request)
        if student is None:
            return error_response("You do not have a student profile.", status_code=404)
        qs = StudentFee.objects.filter(student=student).select_related(
            "academic_year", "program", "semester", "fee_structure", "student"
        ).order_by("-created_at")
        return success_response(StudentFeeSerializer(qs, many=True).data, "Your fees.")
