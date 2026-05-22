# subjects/views.py

from rest_framework import viewsets

from auth_core.permissions import HasPermission, IsAdminRole

from .models import Subject
from .serializers import SubjectReadSerializer, SubjectWriteSerializer


class SubjectViewSet(viewsets.ModelViewSet):
    """
    GET    /api/v1/subjects/            list    (authenticated)
    GET    /api/v1/subjects/{id}/       detail  (authenticated)
    POST   /api/v1/subjects/            create  (admin only)
    PUT    /api/v1/subjects/{id}/       update  (admin only)
    PATCH  /api/v1/subjects/{id}/       partial (admin only)
    DELETE /api/v1/subjects/{id}/       destroy (admin only)
    """
    permission_classes = [HasPermission]

    def get_queryset(self):
        return (
            Subject.objects
            .select_related('teacher', 'teacher__user', 'faculty')
            .all()
        )

    def get_serializer_class(self):
        if self.action in ('list', 'retrieve'):
            return SubjectReadSerializer
        return SubjectWriteSerializer

    def get_permissions(self):
        if self.action in ('list', 'retrieve'):
            return [HasPermission()]
        return [IsAdminRole()]