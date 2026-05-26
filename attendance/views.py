# attendance/views.py

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied

from auth_core.permissions import HasPermission, IsAdminRole

from .models import Attendance
from .services import AttendanceService
from students.models import Teacher, Student
from .serializers import (
    AttendanceReadSerializer,
    AttendanceWriteSerializer,
    AttendanceBulkWriteSerializer,
    AttendanceAdminReadSerializer,
    AttendanceSummaryResponseSerializer,
)

from users.constants import PermissionCodes

class StudentAttendanceViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET  /api/v1/attendance/my/         list    (own records)
    GET  /api/v1/attendance/my/{id}/    detail
    """
    serializer_class   = AttendanceReadSerializer
    permission_classes = [HasPermission]
    required_permission = PermissionCodes.ATTENDANCE_VIEW_OWN

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

    @action(
        detail=False,
        methods=['get'],
        url_path='summary',
        permission_classes=[HasPermission],
    )
    def summary(self, request):
        """
        GET /api/v1/attendance/my/summary/
        GET /api/v1/attendance/my/summary/?subject_id=<id>

        Returns the authenticated student's attendance percentage breakdown.

        Policy: LATE counts as PRESENT (Option A).
        Responds 404 if no Student profile exists for this user.
        Responds 200 with empty subjects list if no attendance has been recorded.
        """
        # Resolve Student profile — user may be authenticated but not a student
        try:
            student = Student.objects.select_related('user').get(user=request.user)
        except Student.DoesNotExist:
            return Response(
                {'detail': 'No student profile found for this account.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        subject_id = request.query_params.get('subject_id')
        if subject_id is not None:
            # Validate it's an integer before passing to the service
            try:
                subject_id = int(subject_id)
            except (ValueError, TypeError):
                return Response(
                    {'detail': 'subject_id must be a valid integer.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        subject_rows    = AttendanceService.compute_subject_summary(student, subject_id)
        overall_pct     = AttendanceService.compute_percentage(
            student,
            subject=subject_id,   # pass raw id; service accepts None or subject
        )

        # overall_percentage when filtering by one subject == that subject's %
        payload = {
            'overall_percentage': overall_pct,
            'subjects':           subject_rows,
        }
        serializer = AttendanceSummaryResponseSerializer(payload)
        return Response(serializer.data, status=status.HTTP_200_OK)


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
    required_permission = PermissionCodes.ATTENDANCE_MARK

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
    
    def perform_destroy(self, instance):       # ← ADD THIS — was missing
        self._assert_is_teacher()
        instance.delete()
# ─────────────────────────────────────────────────────────────
# 3. Admin — full picture, read-only
# ─────────────────────────────────────────────────────────────

class AdminAttendanceViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET  /api/v1/attendance/admin/                            list    (all records)
    GET  /api/v1/attendance/admin/{id}/                       detail
    GET  /api/v1/attendance/admin/summary/?student_id=<id>    per-student summary
    GET  /api/v1/attendance/admin/summary/?student_id=<id>&subject_id=<id>  drill-down
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

    @action(
        detail=False,
        methods=['get'],
        url_path='summary',
        permission_classes=[IsAdminRole],
    )
    def summary(self, request):
        """
        GET /api/v1/attendance/admin/summary/?student_id=<id>
        GET /api/v1/attendance/admin/summary/?student_id=<id>&subject_id=<id>

        Returns attendance percentage breakdown for any student.
        `student_id` is REQUIRED — prevents unfiltered full-table scans.
        `subject_id` is optional for per-subject drill-down.

        Policy: LATE counts as PRESENT (Option A).
        """
        student_id = request.query_params.get('student_id')
        if not student_id:
            return Response(
                {'detail': 'student_id query parameter is required.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            student_id = int(student_id)
        except (ValueError, TypeError):
            return Response(
                {'detail': 'student_id must be a valid integer.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            student = Student.objects.select_related('user').get(pk=student_id)
        except Student.DoesNotExist:
            return Response(
                {'detail': f'Student with id {student_id} not found.'},
                status=status.HTTP_404_NOT_FOUND,
            )

        subject_id = request.query_params.get('subject_id')
        if subject_id is not None:
            try:
                subject_id = int(subject_id)
            except (ValueError, TypeError):
                return Response(
                    {'detail': 'subject_id must be a valid integer.'},
                    status=status.HTTP_400_BAD_REQUEST,
                )

        subject_rows = AttendanceService.compute_subject_summary(student, subject_id)
        overall_pct  = AttendanceService.compute_percentage(student, subject=subject_id)

        payload = {
            'overall_percentage': overall_pct,
            'subjects':           subject_rows,
        }
        serializer = AttendanceSummaryResponseSerializer(payload)
        return Response(serializer.data, status=status.HTTP_200_OK)