# notices/views.py

from django.db.models import Exists, OuterRef
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.response import Response

from auth_core.permissions import HasPermission, IsAdminRole

from .models import Notice, NoticeRead
from .serializers import NoticeReadSerializer, NoticeWriteSerializer
from .services import NoticeService
from users.constants import PermissionCodes


# ─────────────────────────────────────────────────────────────────────────────
# 1. Public — all authenticated users read active notices
# ─────────────────────────────────────────────────────────────────────────────

class NoticeViewSet(viewsets.ReadOnlyModelViewSet):
    """
    GET  /api/v1/notices/                list    (active notices)
    GET  /api/v1/notices/{id}/           detail
    POST /api/v1/notices/{id}/mark_read/ mark this notice as read
    """
    serializer_class    = NoticeReadSerializer
    permission_classes  = [HasPermission]
    required_permission = PermissionCodes.NOTICES_VIEW

    def get_queryset(self):
        """
        Annotates each notice with `is_read` using a single Exists() subquery.
        No N+1 — one SQL query with a correlated subquery handles all rows.
        """
        user = self.request.user
        read_subquery = NoticeRead.objects.filter(
            notice=OuterRef('pk'),
            user=user,
        )
        return (
            Notice.objects
            .filter(is_active=True)
            .annotate(is_read=Exists(read_subquery))
            .order_by('-date_posted')
        )

    @action(
        detail=True,
        methods=['post'],
        url_path='mark_read',
        permission_classes=[HasPermission],
    )
    def mark_read(self, request, pk=None):
        """
        POST /api/v1/notices/{id}/mark_read/

        Idempotent — calling multiple times is safe (get_or_create).
        Returns the full notice representation with is_read=True.
        """
        notice = self.get_object()
        NoticeService.mark_read(notice=notice, user=request.user)

        # Re-fetch with annotation so is_read=True is in the response
        annotated = (
            Notice.objects
            .filter(pk=notice.pk)
            .annotate(
                is_read=Exists(
                    NoticeRead.objects.filter(
                        notice=OuterRef('pk'),
                        user=request.user,
                    )
                )
            )
            .first()
        )
        return Response(
            NoticeReadSerializer(annotated, context={'request': request}).data,
            status=status.HTTP_200_OK,
        )


# ─────────────────────────────────────────────────────────────────────────────
# 2. Admin — full CRUD on all notices (including inactive)
# ─────────────────────────────────────────────────────────────────────────────

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
        # Admin sees all notices; annotate is_read for the admin's own user too
        read_subquery = NoticeRead.objects.filter(
            notice=OuterRef('pk'),
            user=self.request.user,
        )
        return (
            Notice.objects
            .all()
            .annotate(is_read=Exists(read_subquery))
            .order_by('-date_posted')
        )

    def get_serializer_class(self):
        if self.action in ('list', 'retrieve'):
            return NoticeReadSerializer
        return NoticeWriteSerializer

    def perform_create(self, serializer):
        serializer.save()