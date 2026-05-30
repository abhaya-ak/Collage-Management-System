# academics/views.py

from django.utils import timezone
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.response import Response

from auth_core.permissions import HasPermission, IsAdminRole
from auth_core.services.rbac_service import RBACService
from .services import ResultService
from users.constants import PermissionCodes


from .models import Faculty, Routine, ExamRoutine, Result
from .serializers import (
    FacultyReadSerializer,
    FacultyWriteSerializer,
    RoutineReadSerializer,
    RoutineWriteSerializer,
    ExamRoutineReadSerializer,
    ExamRoutineWriteSerializer,
    ResultWriteSerializer,
    ResultStudentReadSerializer,
)

_READ_ACTIONS = ('list', 'retrieve')


# ─────────────────────────────────────────────────────────────
# 1. Faculty
# ─────────────────────────────────────────────────────────────

class FacultyViewSet(viewsets.ModelViewSet):
    """
    list     GET    /api/v1/academics/faculties/
    retrieve GET    /api/v1/academics/faculties/{id}/
    create   POST   /api/v1/academics/faculties/          (admin)
    update   PUT    /api/v1/academics/faculties/{id}/     (admin)
    partial  PATCH  /api/v1/academics/faculties/{id}/     (admin)
    destroy  DELETE /api/v1/academics/faculties/{id}/     (admin)
    """
    queryset           = Faculty.objects.all()
    permission_classes = [HasPermission]
    required_permission = PermissionCodes.ACADEMICS_VIEW_TIMETABLE

    def get_serializer_class(self):
        if self.action in _READ_ACTIONS:
            return FacultyReadSerializer
        return FacultyWriteSerializer

    def get_permissions(self):
        if self.action not in _READ_ACTIONS:
            return [IsAdminRole()]
        return [HasPermission()]


# ─────────────────────────────────────────────────────────────
# 2. Routine
# ─────────────────────────────────────────────────────────────

class RoutineViewSet(viewsets.ModelViewSet):
    """
    list     GET    /api/v1/academics/routines/
    retrieve GET    /api/v1/academics/routines/{id}/
    create   POST   /api/v1/academics/routines/           (admin)
    update   PUT    /api/v1/academics/routines/{id}/      (admin)
    partial  PATCH  /api/v1/academics/routines/{id}/      (admin)
    destroy  DELETE /api/v1/academics/routines/{id}/      (admin)
    """
    permission_classes = [HasPermission]
    required_permission = PermissionCodes.ACADEMICS_VIEW_TIMETABLE

    def get_queryset(self):
        return (
            Routine.objects
            .select_related(
                'subject',
                'subject__faculty',
                'subject__teacher',
                'subject__teacher__user',
            )
            .all()
        )

    def get_serializer_class(self):
        if self.action in _READ_ACTIONS:
            return RoutineReadSerializer
        return RoutineWriteSerializer

    def get_permissions(self):
        if self.action not in _READ_ACTIONS:
            return [IsAdminRole()]
        return [HasPermission()]


# ─────────────────────────────────────────────────────────────
# 3. ExamRoutine
# ─────────────────────────────────────────────────────────────

class ExamRoutineViewSet(viewsets.ModelViewSet):
    """
    list     GET    /api/v1/academics/exam-routines/
    retrieve GET    /api/v1/academics/exam-routines/{id}/
    create   POST   /api/v1/academics/exam-routines/          (admin)
    update   PUT    /api/v1/academics/exam-routines/{id}/     (admin)
    partial  PATCH  /api/v1/academics/exam-routines/{id}/     (admin)
    destroy  DELETE /api/v1/academics/exam-routines/{id}/     (admin)
    """
    permission_classes = [HasPermission]
    required_permission = PermissionCodes.ACADEMICS_VIEW_TIMETABLE

    def get_queryset(self):
        return (
            ExamRoutine.objects
            .select_related('subject', 'subject__faculty')
            .all()
        )

    def get_serializer_class(self):
        if self.action in _READ_ACTIONS:
            return ExamRoutineReadSerializer
        return ExamRoutineWriteSerializer

    def get_permissions(self):
        if self.action not in _READ_ACTIONS:
            return [IsAdminRole()]
        return [HasPermission()]


# ─────────────────────────────────────────────────────────────
# 4. Result  (+ custom publish action)
# ─────────────────────────────────────────────────────────────

class ResultViewSet(viewsets.ModelViewSet):
    """
    list     GET    /api/v1/academics/results/
    retrieve GET    /api/v1/academics/results/{id}/
    create   POST   /api/v1/academics/results/               (admin)
    update   PUT    /api/v1/academics/results/{id}/          (admin)
    partial  PATCH  /api/v1/academics/results/{id}/          (admin)
    destroy  DELETE /api/v1/academics/results/{id}/          (admin — SOFT delete)
    publish  POST   /api/v1/academics/results/{id}/publish/  (admin)

    ?search=<term>       — student username/name, subject code
    ?ordering=<field>    — exam_routine__exam_date, marks_obtained, grade
    """
    permission_classes  = [HasPermission]
    required_permission = PermissionCodes.ACADEMICS_VIEW_RESULT
    filter_backends     = [SearchFilter, OrderingFilter]
    search_fields       = ['student__username', 'student__first_name',
                           'student__last_name',
                           'exam_routine__subject__code',
                           'exam_routine__subject__name', 'grade']
    ordering_fields     = ['exam_routine__exam_date', 'marks_obtained', 'grade']
    ordering            = ['-exam_routine__exam_date']
    
    def get_queryset(self):
        user = self.request.user
        # Exclude soft-deleted rows for everyone.
        # Note: Result.student is a direct FK to AUTH_USER_MODEL (User), so we
        # select_related('student') only — there is no 'student__user' traversal.
        base = Result.objects.filter(is_deleted=False).select_related(
            'student', 'exam_routine', 'exam_routine__subject'
        )
        if RBACService.has_permission(user, PermissionCodes.ACADEMICS_MANAGE_RESULT) or user.is_superuser:
            return base.all()
        return base.filter(student=user, is_published=True)

    def get_serializer_class(self):
        if self.action in _READ_ACTIONS:
            return ResultStudentReadSerializer
        return ResultWriteSerializer

    def get_permissions(self):
        if self.action not in _READ_ACTIONS:
            return [IsAdminRole()]
        return [HasPermission()]

    def perform_destroy(self, instance):
        """
        Soft-delete instead of hard-delete.
        Sets is_deleted=True and records the timestamp.
        The row remains in the DB for audit purposes; it is excluded from
        all normal get_queryset() calls via the is_deleted=False filter.
        """
        instance.is_deleted = True
        instance.deleted_at = timezone.now()
        instance.save(update_fields=['is_deleted', 'deleted_at'])

    @action(
        detail=True,
        methods=['post'],
        permission_classes=[IsAdminRole],
        url_path='publish',
    )
    def publish(self, request, pk=None):
        """POST /api/v1/academics/results/{id}/publish/"""
        result = self.get_object()
        try:
            updated = ResultService.publish(result)
        except ValueError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)
        return Response(
            ResultStudentReadSerializer(updated, context={'request': request}).data,
            status=status.HTTP_200_OK,
        )