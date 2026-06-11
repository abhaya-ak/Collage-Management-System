"""
Faculty API — thin viewset.

    POST   /api/faculty/                      create faculty (account + profile)
    GET    /api/faculty/                      list
    GET    /api/faculty/{id}/                 retrieve (profile + assignments)
    PATCH  /api/faculty/{id}/                 update profile
    POST   /api/faculty/{id}/assign-subject/  assign a subject (curriculum-validated)
    PATCH  /api/faculty/{id}/update-assignment/
    POST   /api/faculty/{id}/remove-assignment/
"""

from rest_framework.decorators import action
from rest_framework.exceptions import NotFound

from apps.faculty import selectors, serializers, services
from apps.faculty.permissions import FACULTY_PERMISSIONS
from shared.responses import success_response
from shared.viewsets import BaseRBACViewSet


class FacultyViewSet(BaseRBACViewSet):
    permission_map = FACULTY_PERMISSIONS
    http_method_names = ["get", "post", "patch", "head", "options"]

    search_fields = ["employee_id", "user__email", "designation"]
    ordering_fields = ["employee_id", "join_date", "created_at"]
    filterset_fields = ["status"]

    def get_queryset(self):
        if self.action == "retrieve":
            return selectors.faculty_detail_qs()
        return selectors.faculty_list()

    def get_serializer_class(self):
        if self.action in ("update", "partial_update"):
            return serializers.FacultyUpdateSerializer
        if self.action == "retrieve":
            return serializers.FacultyDetailSerializer
        return serializers.FacultySerializer

    # --- create routes through the service (also creates the user) -----------
    def create(self, request, *args, **kwargs):
        ser = serializers.FacultyCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        faculty = services.create_faculty(actor=request.user, **ser.validated_data)
        data = serializers.FacultyDetailSerializer(
            selectors.get_faculty_profile(faculty.pk)
        ).data
        return success_response(data, "Faculty created successfully.", 201)

    # --- assignment management ----------------------------------------------
    def _owned_assignment(self, faculty, assignment):
        if assignment.faculty_id != faculty.id:
            raise NotFound("Assignment does not belong to this faculty.")
        return assignment

    @action(detail=True, methods=["post"], url_path="assign-subject")
    def assign_subject(self, request, pk=None):
        faculty = self.get_object()
        ser = serializers.AssignSubjectSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        assignment = services.assign_subject(faculty=faculty, actor=request.user, **ser.validated_data)
        return success_response(
            serializers.FacultyAssignmentSerializer(assignment).data,
            "Subject assigned successfully.", 201,
        )

    @action(detail=True, methods=["patch"], url_path="update-assignment")
    def update_assignment(self, request, pk=None):
        faculty = self.get_object()
        ser = serializers.UpdateAssignmentSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        data = dict(ser.validated_data)
        assignment = self._owned_assignment(faculty, data.pop("assignment"))
        assignment = services.update_assignment(assignment, actor=request.user, **data)
        return success_response(
            serializers.FacultyAssignmentSerializer(assignment).data,
            "Assignment updated successfully.",
        )

    @action(detail=True, methods=["post"], url_path="remove-assignment")
    def remove_assignment(self, request, pk=None):
        faculty = self.get_object()
        ser = serializers.RemoveAssignmentSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        assignment = self._owned_assignment(faculty, ser.validated_data["assignment"])
        services.remove_assignment(assignment, actor=request.user)
        return success_response(message="Assignment removed successfully.")
