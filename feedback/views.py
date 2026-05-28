# feedback/views.py
from rest_framework import viewsets, mixins, status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from auth_core.permissions import HasPermission, IsAdminRole
from .models import Feedback
from .services import FeedbackService
from students.models import Student
from .serializers import (
    FeedbackWriteSerializer,
    FeedbackStudentReadSerializer,
    FeedbackAdminReadSerializer,
    FeedbackReplySerializer,
)
from users.constants import PermissionCodes


# ─────────────────────────────────────────────────────────────────────────────
# 1. Student — submit + view own submissions
# ─────────────────────────────────────────────────────────────────────────────

class FeedbackViewSet(
    mixins.CreateModelMixin,
    viewsets.GenericViewSet,
):
    """
    POST  /api/v1/feedback/submit/     submit feedback (student only)
    """
    serializer_class   = FeedbackWriteSerializer
    permission_classes = [HasPermission]

    def create(self, request):
        """Submit a new feedback item. Only registered students can submit."""
        try:
            student = Student.objects.get(user=request.user)
        except Student.DoesNotExist:
            raise PermissionDenied("Only registered students can submit feedback.")

        serializer = FeedbackWriteSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(student=student)

        return Response(
            FeedbackStudentReadSerializer(
                serializer.instance,
                context={'request': request},
            ).data,
            status=status.HTTP_201_CREATED,
        )


class StudentFeedbackViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET  /api/v1/feedback/my/           list   (own submissions, newest first)
    GET  /api/v1/feedback/my/{id}/      detail

    Students see their own submissions including status and admin reply.
    """
    serializer_class    = FeedbackStudentReadSerializer
    permission_classes  = [HasPermission]
    required_permission = PermissionCodes.FEEDBACK_SUBMIT  # same perm as submit

    def get_queryset(self):
        return (
            Feedback.objects
            .filter(student__user=self.request.user)
            .select_related(
                'student', 'student__user',
                'target_teacher',
                'replied_by',
            )
            .order_by('-submitted_at')
        )

class AdminFeedbackViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET   /api/v1/feedback/admin/              list    (all, newest first)
    GET   /api/v1/feedback/admin/{id}/         detail
    POST  /api/v1/feedback/admin/{id}/reply/   update status + add reply
    """
    serializer_class   = FeedbackAdminReadSerializer
    permission_classes = [IsAdminRole]

    def get_queryset(self):
        # FIX: was select_related('submitted_by', 'submitted_by__user')
        # The FK is 'student' (→ Student model), not 'submitted_by'.
        return (
            Feedback.objects
            .select_related(
                'student',
                'student__user',
                'target_teacher',
                'replied_by',
            )
            .order_by('-submitted_at')
        )

    @action(
        detail=True,
        methods=['post'],
        url_path='reply',
        permission_classes=[IsAdminRole],
    )
    def reply(self, request, pk=None):
        """
        POST /api/v1/feedback/admin/{id}/reply/

        Admin sets the feedback status and optionally provides a reply message.
        Rules:
          - RESOLVED / CLOSED → admin_reply is required.
          - PENDING / REVIEWED → admin_reply is optional.
        """
        feedback   = self.get_object()
        serializer = FeedbackReplySerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)

        try:
            updated = FeedbackService.reply(
                feedback    = feedback,
                status      = serializer.validated_data['status'],
                admin_reply = serializer.validated_data.get('admin_reply', ''),
                replied_by  = request.user,
            )
        except ValueError as e:
            return Response({'detail': str(e)}, status=status.HTTP_400_BAD_REQUEST)

        return Response(
            FeedbackAdminReadSerializer(updated, context={'request': request}).data,
            status=status.HTTP_200_OK,
        )