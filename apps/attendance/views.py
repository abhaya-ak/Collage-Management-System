"""
Attendance API — thin viewset.

    POST /api/attendance/sessions/             create session
    GET  /api/attendance/sessions/             list (teachers see only their own)
    GET  /api/attendance/sessions/{id}/        retrieve (session + records)
    POST /api/attendance/sessions/{id}/mark/   mark/update records
    POST /api/attendance/sessions/{id}/lock/   lock the session
"""

from rest_framework.decorators import action

from apps.attendance import selectors, serializers, services
from apps.attendance.permissions import ATTENDANCE_PERMISSIONS
from apps.faculty.models import Faculty
from shared.responses import success_response
from shared.viewsets import BaseRBACViewSet


class AttendanceSessionViewSet(BaseRBACViewSet):
    permission_map = ATTENDANCE_PERMISSIONS
    http_method_names = ["get", "post", "head", "options"]

    filterset_fields = ["faculty_assignment", "attendance_date", "is_locked"]
    ordering_fields = ["attendance_date", "created_at"]

    def get_queryset(self):
        qs = selectors.session_detail_qs() if self.action == "retrieve" else selectors.session_list()
        user = self.request.user
        # Managers/superusers see everything; teachers see only their own sessions.
        if user.is_superuser or user.has_permission("manage_attendance"):
            return qs
        faculty = Faculty.objects.filter(user=user).first()
        if faculty:
            return qs.filter(faculty_assignment__faculty=faculty)
        return qs.none()

    def get_serializer_class(self):
        if self.action == "retrieve":
            return serializers.AttendanceSessionDetailSerializer
        return serializers.AttendanceSessionSerializer

    def create(self, request, *args, **kwargs):
        ser = serializers.CreateSessionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        session = services.create_session(actor=request.user, **ser.validated_data)
        data = serializers.AttendanceSessionDetailSerializer(session).data
        return success_response(data, "Attendance session created.", 201)

    @action(detail=True, methods=["post"])
    def mark(self, request, pk=None):
        session = self.get_object()
        ser = serializers.MarkAttendanceSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        session = services.mark_attendance(session, ser.validated_data["records"], actor=request.user)
        data = serializers.AttendanceSessionDetailSerializer(
            selectors.session_detail_qs().get(pk=session.pk)
        ).data
        return success_response(data, "Attendance marked.")

    @action(detail=True, methods=["post"])
    def lock(self, request, pk=None):
        session = self.get_object()
        session = services.lock_session(session, actor=request.user)
        return success_response(
            serializers.AttendanceSessionSerializer(session).data,
            "Attendance session locked.",
        )
