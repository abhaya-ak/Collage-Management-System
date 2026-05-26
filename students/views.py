# students/views.py

from rest_framework import viewsets
from rest_framework.exceptions import PermissionDenied

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
    GET    /api/v1/students/leaves/         list    (own records)
    GET    /api/v1/students/leaves/{id}/    detail
    POST   /api/v1/students/leaves/         submit
    PUT    /api/v1/students/leaves/{id}/    update  (pending only)
    PATCH  /api/v1/students/leaves/{id}/    partial
    DELETE /api/v1/students/leaves/{id}/    cancel
    """
    permission_classes = [HasPermission]
    required_permission = PermissionCodes.STUDENTS_VIEW_ALL

    def get_serializer_class(self):
        if self.action in ('create', 'update', 'partial_update'):
            return LeaveRequestWriteSerializer
        return LeaveRequestReadSerializer

    def get_queryset(self):
        return (
            LeaveRequest.objects
            .filter(student__user=self.request.user)
            .select_related('student', 'student__user')
        )

    def perform_create(self, serializer):
        try:
            student = Student.objects.get(user=self.request.user)
        except Student.DoesNotExist:
            raise PermissionDenied("Only registered students can submit leave requests.")
        serializer.save(student=student)


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