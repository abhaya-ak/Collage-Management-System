# Create your views here.

from rest_framework import viewsets, permissions
from .models import Notice
from .serializers import NoticeSerializer

class AdminNoticeViewSet(viewsets.ModelViewSet):
    """
    GET /api/v1/notices/ -> List all notices
    POST /api/v1/notices/ -> Create a new notice
    PUT /api/v1/notices/{id}/ -> Update a notice
    DELETE /api/v1/notices/{id}/ -> Delete a notice
    """
    serializer_class = NoticeSerializer
    # Order by newest first
    queryset = Notice.objects.all().order_by('-date_posted')

    def get_permissions(self):
        # If the request is POST, PUT, or DELETE -> Must be an Admin
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [permissions.IsAdminUser()]
        
        # If the request is GET -> Any logged-in user can view
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        # Optional Advanced Logic: Filter what users see based on their role!
        user = self.request.user
        
        # Admins see absolutely everything
        if user.is_staff:
            return Notice.objects.all().order_by('-date_posted')
            
        # Teachers see 'ALL' and 'TEACHERS' notices
        if hasattr(user, 'teacher'):
            return Notice.objects.filter(target_audience__in=['ALL', 'TEACHERS']).order_by('-date_posted')
            
        # Students see 'ALL' and 'STUDENTS' notices
        if hasattr(user, 'student'):
            return Notice.objects.filter(target_audience__in=['ALL', 'STUDENTS']).order_by('-date_posted')
            
        return Notice.objects.none() # Fallback for safety