# attendance/views.py

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied

from auth_core.permissions import HasPermission, IsAdminRole

from .models import Attendance
from students.models import Teacher
from .serializers import (
    AttendanceReadSerializer,
    AttendanceWriteSerializer,
    AttendanceBulkWriteSerializer,
    AttendanceAdminReadSerializer,
)


# ─────────────────────────────────────────────────────────────
# 1. Student — own attendance records (read-only)
# ─────────────────────────────────────────────────────────────

class StudentAttendanceViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET  /api/v1/attendance/my/         list    (own records)
    GET  /api/v1/attendance/my/{id}/    detail
    """
    serializer_class   = AttendanceReadSerializer
    permission_classes = [HasPermission]

    def get_queryset(self):
        return (
            Attendance.objects
            .filter(student__user=self.request.user)
            .select_related(
                'student', 'student__user',
                'subject', 'marked_by',
            )
            .order_by('-date')
        )


# ─────────────────────────────────────────────────────────────
# 2. Teacher — mark single + bulk
# ─────────────────────────────────────────────────────────────

class TeacherAttendanceViewSet(viewsets.ModelViewSet):
    """
    POST   /api/v1/attendance/mark/             mark single student
    POST   /api/v1/attendance/mark/bulk/        mark entire class at once
    GET    /api/v1/attendance/mark/             list   (teacher's own marks)
    GET    /api/v1/attendance/mark/{id}/        detail
    PUT    /api/v1/attendance/mark/{id}/        correct a record
    PATCH  /api/v1/attendance/mark/{id}/        partial correct
    DELETE /api/v1/attendance/mark/{id}/        remove a record
    """
    permission_classes = [HasPermission]

    def get_serializer_class(self):
        if self.action == 'bulk':
            return AttendanceBulkWriteSerializer
        if self.action in ('list', 'retrieve'):
            return AttendanceReadSerializer
        return AttendanceWriteSerializer

    def get_queryset(self):
        return (
            Attendance.objects
            .filter(marked_by=self.request.user)
            .select_related(
                'student', 'student__user',
                'subject', 'marked_by',
            )
            .order_by('-date')
        )

    def perform_create(self, serializer):
        self._assert_is_teacher()
        serializer.save(marked_by=self.request.user)

    def perform_update(self, serializer):
        self._assert_is_teacher()
        serializer.save(marked_by=self.request.user)

    def _assert_is_teacher(self):
        if not Teacher.objects.filter(user=self.request.user).exists():
            raise PermissionDenied("Only registered teachers can mark attendance.")

    @action(
        detail=False,
        methods=['post'],
        url_path='bulk',
        serializer_class=AttendanceBulkWriteSerializer,
    )
    def bulk(self, request):
        """POST /api/v1/attendance/mark/bulk/"""
        self._assert_is_teacher()
        serializer = AttendanceBulkWriteSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        records = serializer.save()
        return Response(
            AttendanceReadSerializer(records, many=True, context={'request': request}).data,
            status=status.HTTP_201_CREATED,
        )


# ─────────────────────────────────────────────────────────────
# 3. Admin — full picture, read-only
# ─────────────────────────────────────────────────────────────

class AdminAttendanceViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET  /api/v1/attendance/admin/          list    (all records)
    GET  /api/v1/attendance/admin/{id}/     detail
    """
    serializer_class   = AttendanceAdminReadSerializer
    permission_classes = [IsAdminRole]

    def get_queryset(self):
        return (
            Attendance.objects
            .select_related(
                'student', 'student__user',
                'subject', 'marked_by',
            )
            .order_by('-date')
        )