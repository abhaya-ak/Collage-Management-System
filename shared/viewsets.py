"""
BaseRBACViewSet — reusable CRUD viewset that:
  * enforces action-based RBAC (ActionPermission + permission_map)
  * routes writes through the service layer (create_service / update_service)
  * soft-deletes on destroy
  * returns every response in the standardized envelope

Subclasses set: queryset/selector, serializer_class, permission_map, and
optionally create_service / update_service callables.
"""

from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated

from shared.permissions import ActionPermission
from shared.responses import success_response


class BaseRBACViewSet(viewsets.ModelViewSet):
    permission_classes = [IsAuthenticated, ActionPermission]
    permission_map: dict = {}

    # Optional service hooks: callables(validated_data) / (instance, validated_data)
    create_service = None
    update_service = None

    # --- write operations go through services -------------------------------
    def perform_create(self, serializer):
        if self.create_service:
            serializer.instance = self.create_service(serializer.validated_data)
        else:
            serializer.save()

    def perform_update(self, serializer):
        if self.update_service:
            serializer.instance = self.update_service(
                serializer.instance, serializer.validated_data
            )
        else:
            serializer.save()

    def perform_destroy(self, instance):
        instance.delete()  # soft delete (SoftDeleteMixin)

    # --- standardized envelope on every response ----------------------------
    def list(self, request, *args, **kwargs):
        resp = super().list(request, *args, **kwargs)
        return success_response(resp.data, "Fetched successfully.", resp.status_code)

    def retrieve(self, request, *args, **kwargs):
        resp = super().retrieve(request, *args, **kwargs)
        return success_response(resp.data, "Fetched successfully.", resp.status_code)

    def create(self, request, *args, **kwargs):
        resp = super().create(request, *args, **kwargs)
        return success_response(resp.data, "Created successfully.", resp.status_code)

    def update(self, request, *args, **kwargs):
        resp = super().update(request, *args, **kwargs)
        return success_response(resp.data, "Updated successfully.", resp.status_code)

    def destroy(self, request, *args, **kwargs):
        super().destroy(request, *args, **kwargs)
        return success_response(message="Deleted successfully.", status_code=200)
