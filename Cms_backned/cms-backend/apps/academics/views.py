"""
Academics viewsets — thin. Queryset from selectors, writes via services,
RBAC via permission_map, standardized responses from BaseRBACViewSet.
"""

from apps.academics import permissions as perms
from apps.academics import selectors, serializers, services
from apps.academics.models import Program, Section, Semester, Subject
from shared.viewsets import BaseRBACViewSet


class AcademicYearViewSet(BaseRBACViewSet):
    serializer_class = serializers.AcademicYearSerializer
    permission_map = perms.ACADEMIC_YEAR_PERMISSIONS
    create_service = staticmethod(services.create_academic_year)
    update_service = staticmethod(services.update_academic_year)
    search_fields = ["name"]
    ordering_fields = ["start_date", "name"]

    def get_queryset(self):
        return selectors.academic_year_list()


class ProgramViewSet(BaseRBACViewSet):
    serializer_class = serializers.ProgramSerializer
    permission_map = perms.PROGRAM_PERMISSIONS
    search_fields = ["code", "name"]
    ordering_fields = ["code", "name"]

    def get_queryset(self):
        return selectors.program_list()

    def perform_create(self, serializer):
        serializer.instance = services.create_instance(Program, serializer.validated_data)

    def perform_update(self, serializer):
        serializer.instance = services.update_instance(serializer.instance, serializer.validated_data)


class SemesterViewSet(BaseRBACViewSet):
    serializer_class = serializers.SemesterSerializer
    permission_map = perms.SEMESTER_PERMISSIONS
    ordering_fields = ["number"]

    def get_queryset(self):
        return selectors.semester_list()

    def perform_create(self, serializer):
        serializer.instance = services.create_instance(Semester, serializer.validated_data)

    def perform_update(self, serializer):
        serializer.instance = services.update_instance(serializer.instance, serializer.validated_data)


class SubjectViewSet(BaseRBACViewSet):
    serializer_class = serializers.SubjectSerializer
    permission_map = perms.SUBJECT_PERMISSIONS
    search_fields = ["code", "name"]
    ordering_fields = ["code", "name"]

    def get_queryset(self):
        return selectors.subject_list()

    def perform_create(self, serializer):
        serializer.instance = services.create_instance(Subject, serializer.validated_data)

    def perform_update(self, serializer):
        serializer.instance = services.update_instance(serializer.instance, serializer.validated_data)


class SectionViewSet(BaseRBACViewSet):
    serializer_class = serializers.SectionSerializer
    permission_map = perms.SECTION_PERMISSIONS
    filterset_fields = ["program", "semester"]
    ordering_fields = ["name"]

    def get_queryset(self):
        return selectors.section_list()

    def perform_create(self, serializer):
        serializer.instance = services.create_instance(Section, serializer.validated_data)

    def perform_update(self, serializer):
        serializer.instance = services.update_instance(serializer.instance, serializer.validated_data)


class ProgramSemesterSubjectViewSet(BaseRBACViewSet):
    serializer_class = serializers.ProgramSemesterSubjectSerializer
    permission_map = perms.CURRICULUM_PERMISSIONS
    filterset_fields = ["program", "semester", "subject", "is_elective"]

    def get_queryset(self):
        return selectors.curriculum_list()

    def perform_create(self, serializer):
        from apps.academics.models import ProgramSemesterSubject
        serializer.instance = services.create_instance(ProgramSemesterSubject, serializer.validated_data)

    def perform_update(self, serializer):
        serializer.instance = services.update_instance(serializer.instance, serializer.validated_data)
