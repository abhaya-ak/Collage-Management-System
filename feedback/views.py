# feedback/views.py

from rest_framework import viewsets, mixins
from rest_framework.exceptions import PermissionDenied

from auth_core.permissions import HasPermission, IsAdminRole

from .models import Feedback
from students.models import Student
from .serializers import (
    FeedbackWriteSerializer,
    FeedbackStudentReadSerializer,
    FeedbackAdminReadSerializer,
)


class FeedbackViewSet(mixins.CreateModelMixin, viewsets.GenericViewSet):
    """
    POST  /api/v1/feedback/     submit feedback   (student only)

    CreateModelMixin is required so the DRF router wires up POST.
    Students submit; only admin reads (via AdminFeedbackViewSet).
    """
    serializer_class   = FeedbackWriteSerializer
    permission_classes = [HasPermission]

    def create(self, request):
        from rest_framework.response import Response
        from rest_framework import status

        try:
            student = Student.objects.get(user=request.user)
        except Student.DoesNotExist:
            raise PermissionDenied("Only registered students can submit feedback.")

        serializer = FeedbackWriteSerializer(
            data=request.data,
            context={'request': request},
        )
        serializer.is_valid(raise_exception=True)
        serializer.save(submitted_by=student)

        return Response(
            FeedbackStudentReadSerializer(
                serializer.instance,
                context={'request': request},
            ).data,
            status=status.HTTP_201_CREATED,
        )


class AdminFeedbackViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET  /api/v1/feedback/admin/            list    (all feedback)
    GET  /api/v1/feedback/admin/{id}/       detail
    """
    serializer_class   = FeedbackAdminReadSerializer
    permission_classes = [IsAdminRole]

    def get_queryset(self):
        return (
            Feedback.objects
            .select_related(
                'submitted_by',
                'submitted_by__user',
                'target_teacher',
            )
            .order_by('-submitted_at')
        )