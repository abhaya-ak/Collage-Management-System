# notices/views.py

from rest_framework import viewsets

from auth_core.permissions import HasPermission, IsAdminRole

from .models import Notice
from .serializers import NoticeReadSerializer, NoticeWriteSerializer


class NoticeViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET  /api/v1/notices/           list    (active notices — all authenticated)
    GET  /api/v1/notices/{id}/      detail
    """
    serializer_class   = NoticeReadSerializer
    permission_classes = [HasPermission]

    def get_queryset(self):
        return Notice.objects.filter(is_active=True)


class AdminNoticeViewSet(viewsets.ModelViewSet):
    """
    GET    /api/v1/notices/admin/           list    (all, incl. inactive)
    GET    /api/v1/notices/admin/{id}/      detail
    POST   /api/v1/notices/admin/           create
    PUT    /api/v1/notices/admin/{id}/      update
    PATCH  /api/v1/notices/admin/{id}/      partial update
    DELETE /api/v1/notices/admin/{id}/      delete
    """
    permission_classes = [IsAdminRole]

    def get_queryset(self):
        return Notice.objects.all()

    def get_serializer_class(self):
        if self.action in ('list', 'retrieve'):
            return NoticeReadSerializer
        return NoticeWriteSerializer

    def perform_create(self, serializer):
        serializer.save()