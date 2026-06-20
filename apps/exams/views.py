"""
Exam/Result API — thin viewsets. Writes go through the service layer
(enter_marks / generate_result / publish_result); reads via selectors.
"""

from django.db.models import Q
from rest_framework.decorators import action
from rest_framework.exceptions import MethodNotAllowed

from apps.exams import selectors, serializers, services
from apps.exams.permissions import (
    EXAM_PERMISSIONS,
    EXAM_SCHEDULE_PERMISSIONS,
    MARK_PERMISSIONS,
    RESULT_PERMISSIONS,
)
from apps.faculty.models import Faculty, FacultyAssignment
from apps.students.models import Student, StudentEnrollment
from shared.responses import success_response
from shared.viewsets import BaseRBACViewSet


def _is_admin(user):
    return user.is_superuser or user.has_permission("manage_exam")


class ExamViewSet(BaseRBACViewSet):
    serializer_class = serializers.ExamSerializer
    permission_map = EXAM_PERMISSIONS
    filterset_fields = ["academic_year", "program", "semester", "exam_type", "status"]
    search_fields = ["name"]
    ordering_fields = ["start_date", "name"]

    def get_queryset(self):
        if self.action == "retrieve":
            return selectors.exam_detail_qs()
        return selectors.exam_list()


class ExamScheduleViewSet(BaseRBACViewSet):
    serializer_class = serializers.ExamScheduleSerializer
    permission_map = EXAM_SCHEDULE_PERMISSIONS
    filterset_fields = ["exam", "subject", "section"]
    ordering_fields = ["exam_date", "start_time"]

    def get_queryset(self):
        return selectors.exam_schedule_list()


class MarkViewSet(BaseRBACViewSet):
    serializer_class = serializers.MarkSerializer
    permission_map = MARK_PERMISSIONS
    http_method_names = ["get", "post", "head", "options"]
    filterset_fields = ["student", "exam_schedule", "is_published"]

    def get_queryset(self):
        user = self.request.user
        qs = selectors.mark_list()
        if _is_admin(user):
            return qs
        student = Student.objects.filter(user=user).first()
        if student:
            return qs.filter(student=student)
        faculty = Faculty.objects.filter(user=user).first()
        if faculty:
            pairs = FacultyAssignment.objects.filter(faculty=faculty).values(
                "subject_id", "section_id"
            )
            q = Q()
            for p in pairs:
                q |= Q(exam_schedule__subject_id=p["subject_id"],
                       exam_schedule__section_id=p["section_id"])
            return qs.filter(q) if pairs else qs.none()
        return qs.none()

    def create(self, request, *args, **kwargs):
        raise MethodNotAllowed("POST", detail="Use POST /api/exams/marks/enter/ instead.")

    @action(detail=False, methods=["post"], url_path="enter")
    def enter(self, request):
        ser = serializers.MarkEntrySerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        mark = services.enter_marks(actor=request.user, **ser.validated_data)
        return success_response(serializers.MarkSerializer(mark).data, "Marks entered.", 201)


class ResultViewSet(BaseRBACViewSet):
    permission_map = RESULT_PERMISSIONS
    http_method_names = ["get", "post", "head", "options"]
    filterset_fields = ["student", "exam", "published"]

    def get_serializer_class(self):
        if self.action == "retrieve":
            return serializers.ResultDetailSerializer
        return serializers.ResultSerializer

    def get_queryset(self):
        user = self.request.user
        qs = selectors.result_detail_qs() if self.action == "retrieve" else selectors.result_list()
        if _is_admin(user):
            return qs
        student = Student.objects.filter(user=user).first()
        if student:
            return qs.filter(student=student)
        faculty = Faculty.objects.filter(user=user).first()
        if faculty:
            section_ids = FacultyAssignment.objects.filter(faculty=faculty).values_list(
                "section_id", flat=True
            )
            student_ids = StudentEnrollment.objects.filter(
                section_id__in=section_ids, status="ACTIVE"
            ).values_list("student_id", flat=True)
            return qs.filter(student_id__in=student_ids)
        return qs.none()

    def create(self, request, *args, **kwargs):
        raise MethodNotAllowed("POST", detail="Use POST /api/exams/results/generate/ instead.")

    @action(detail=False, methods=["post"], url_path="generate")
    def generate(self, request):
        ser = serializers.GenerateResultSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        result = services.generate_result(actor=request.user, **ser.validated_data)
        data = serializers.ResultDetailSerializer(
            selectors.result_detail_qs().get(pk=result.pk)
        ).data
        return success_response(data, "Result generated.", 201)

    @action(detail=True, methods=["post"])
    def publish(self, request, pk=None):
        result = self.get_object()
        result = services.publish_result(result, actor=request.user)
        return success_response(serializers.ResultSerializer(result).data, "Result published.")
