from rest_framework import viewsets, permissions
from .models import Subject
from .serializers import SubjectReadSerializer, SubjectWriteSerializer

class SubjectViewSet(viewsets.ModelViewSet):
    """
    Handles all 5 endpoints:
    GET /api/v1/subjects/ -> List subjects
    POST /api/v1/subjects/ -> Create subject
    GET /api/v1/subjects/{id}/ -> Subject detail
    PUT /api/v1/subjects/{id}/ -> Update subject
    DELETE /api/v1/subjects/{id}/ -> Delete subject
    """
    queryset = Subject.objects.all().order_by('name')

    def get_serializer_class(self):
        # Use Write Serializer for modifying data (POST, PUT, PATCH)
        if self.action in ['create', 'update', 'partial_update']:
            return SubjectWriteSerializer
        # Use Read Serializer for viewing data (GET)
        return SubjectReadSerializer

    def get_permissions(self):
        # Security: Only Staff/Admins can Create, Update, or Delete subjects
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [permissions.IsAdminUser()]
        
        # Any authenticated user (Student, Teacher, Admin) can view subjects
        return [permissions.IsAuthenticated()]