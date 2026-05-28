# students/views.py

from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from auth_core.permissions import HasPermission, IsAdminRole
from auth_core.services.rbac_service import RBACService

from .models import Student, Teacher, LeaveRequest
from academics.models import Result, Routine
from academics.serializers import ResultStudentReadSerializer, RoutineReadSerializer
from feedback.models import Feedback
from feedback.serializers import FeedbackTeacherReadSerializer
from users.constants import PermissionCodes

from .serializers import (
    StudentProfileSerializer,
    StudentWriteSerializer,
    TeacherSerializer,
    LeaveRequestReadSerializer,
    LeaveRequestWriteSerializer,
)
from .services import LeaveRequestService

_READ_ACTIONS = ('list', 'retrieve')


class StudentProfileViewSet(viewsets.ModelViewSet):
    """
    GET    /api/v1/students/profiles/           list    (authenticated)
    GET    /api/v1/students/profiles/{id}/      detail  (authenticated)
    POST   /api/v1/students/profiles/           create  (admin only)
    PUT    /api/v1/students/profiles/{id}/      update  (admin only)
    PATCH  /api/v1/students/profiles/{id}/      partial (admin only)
    DELETE /api/v1/students/profiles/{id}/      destroy (admin only)
    """
    def get_queryset(self):
        user = self.request.user
        # Admin, teacher, accounts, receptionist — anyone with STUDENTS_VIEW_ALL
        if RBACService.has_permission(user, PermissionCodes.STUDENTS_VIEW_ALL) \
           or user.is_superuser:
            return Student.objects.select_related('user').all()
        # Students see only their own profile
        return Student.objects.select_related('user').filter(user=user)
    
    permission_classes = [HasPermission]
    required_permission = PermissionCodes.STUDENTS_VIEW_ALL

    def get_serializer_class(self):
        if self.action in _READ_ACTIONS:
            return StudentProfileSerializer
        return StudentWriteSerializer

    def get_permissions(self):
        if self.action in _READ_ACTIONS:
            return [HasPermission()]
        return [IsAdminRole()]


class TeacherViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET  /api/v1/students/teachers/         list    (authenticated)
    GET  /api/v1/students/teachers/{id}/    detail  (authenticated)
    """
    queryset           = Teacher.objects.select_related('user').all()
    serializer_class   = TeacherSerializer
    permission_classes = [HasPermission]
    required_permission = PermissionCodes.STUDENTS_VIEW_ALL


class LeaveRequestViewSet(viewsets.ModelViewSet):
    """
    GET    /api/v1/students/leaves/                 list    (own records for students;
                                                             all records for admins)
    GET    /api/v1/students/leaves/{id}/            detail
    POST   /api/v1/students/leaves/                 submit  (students only)
    PUT    /api/v1/students/leaves/{id}/            update  (student, pending only)
    PATCH  /api/v1/students/leaves/{id}/            partial
    DELETE /api/v1/students/leaves/{id}/            cancel
    POST   /api/v1/students/leaves/{id}/approve/    approve (admin only)
    POST   /api/v1/students/leaves/{id}/reject/     reject  (admin only)
    """
    permission_classes = [HasPermission]
    required_permission = PermissionCodes.STUDENTS_VIEW_ALL

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return LeaveRequestWriteSerializer
        return LeaveRequestReadSerializer

    def get_queryset(self):
        user = self.request.user
        # Admins (and superusers) see every leave request so they can review them.
        if user.is_superuser or RBACService.has_permission(user, PermissionCodes.STUDENTS_MANAGE):
            return (
                LeaveRequest.objects
                .select_related('student', 'student__user')
                .all()
            )
        # Students see only their own leave requests.
        return (
            LeaveRequest.objects
            .filter(student__user=user)
            .select_related('student', 'student__user')
        )

    def perform_create(self, serializer):
        """Only registered students may submit leave requests."""
        try:
            student = Student.objects.get(user=self.request.user)
        except Student.DoesNotExist:
            raise PermissionDenied("Only registered students can submit leave requests.")
        serializer.save(student=student)

    # ── Admin-only status transitions ─────────────────────────────────────────

    @action(detail=True, methods=['post'], url_path='approve',
            permission_classes=[IsAdminRole])
    def approve(self, request, pk=None):
        """
        POST /api/v1/students/leaves/{id}/approve/

        Approves a pending leave request.
        Returns 200 with the updated leave object or 400 if already approved.
        """
        leave = self.get_object()   # handles 404 automatically
        try:
            updated = LeaveRequestService.approve(leave)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        serializer = LeaveRequestReadSerializer(updated, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='reject',
            permission_classes=[IsAdminRole])
    def reject(self, request, pk=None):
        """
        POST /api/v1/students/leaves/{id}/reject/

        Reverts an approved leave request back to pending.
        Returns 200 with the updated leave object or 400 if already pending.
        """
        leave = self.get_object()   # handles 404 automatically
        try:
            updated = LeaveRequestService.reject(leave)
        except ValueError as exc:
            return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        serializer = LeaveRequestReadSerializer(updated, context={'request': request})
        return Response(serializer.data, status=status.HTTP_200_OK)


class StudentResultViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET  /api/v1/students/results/          list    (own + published)
    GET  /api/v1/students/results/{id}/     detail
    """
    serializer_class   = ResultStudentReadSerializer
    permission_classes = [HasPermission]
    required_permission = PermissionCodes.STUDENTS_VIEW_ALL

    def get_queryset(self):
        return (
            Result.objects
            .filter(student=self.request.user, is_published=True)
            .select_related('exam_routine', 'exam_routine__subject')
        )


class TeacherRoutineViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET  /api/v1/students/teacher-routines/         list    (own subjects)
    GET  /api/v1/students/teacher-routines/{id}/    detail
    """
    serializer_class   = RoutineReadSerializer
    permission_classes = [HasPermission]
    required_permission = PermissionCodes.STUDENTS_VIEW_ALL

    def get_queryset(self):
        return (
            Routine.objects
            .filter(subject__teacher__user=self.request.user)
            .select_related(
                'subject',
                'subject__faculty',
                'subject__teacher',
                'subject__teacher__user',
            )
        )


class TeacherFeedbackViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET  /api/v1/students/teacher-feedback/         list    (targeted at self)
    GET  /api/v1/students/teacher-feedback/{id}/    detail
    """
    serializer_class   = FeedbackTeacherReadSerializer
    permission_classes = [HasPermission]
    required_permission = PermissionCodes.STUDENTS_VIEW_ALL

    def get_queryset(self):
        return (
            Feedback.objects
            .filter(target_teacher=self.request.user)
            .order_by('-submitted_at')
        )