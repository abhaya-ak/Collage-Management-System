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

from rest_framework.decorators import action
from rest_framework.exceptions import MethodNotAllowed

from apps.students import selectors, serializers, services
from apps.students.permissions import STUDENT_PERMISSIONS
from shared.responses import success_response
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
        enrollment_keys = ["academic_year", "program", "semester", "section", "enrollment_date"]

        student = services.admit_student(
            account_email=v["account_email"],
            password=v["password"],
            registration_number=v["registration_number"],
            profile={k: v[k] for k in profile_keys},
            enrollment={k: v[k] for k in enrollment_keys},
            actor=request.user,
        )
        data = serializers.StudentDetailSerializer(
            selectors.get_student_profile(student.pk)
        ).data
        return success_response(data, "Student admitted successfully.", 201)

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
