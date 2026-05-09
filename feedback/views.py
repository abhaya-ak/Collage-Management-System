from rest_framework import viewsets, permissions
from .models import Feedback, Student
from .serializers import FeedbackWriteSerializer, FeedbackReadSerializer

class FeedbackViewSet(viewsets.ModelViewSet):
    """
    POST /api/v1/feedback/ -> Submit feedback (Students)
    GET /api/v1/feedback/ -> View all feedback (Admins)
    """
    queryset = Feedback.objects.all().order_by('-submitted_at')
    
    # Strictly lock down the HTTP methods. No edits or deletions allowed!
    http_method_names = ['get', 'post']

    def get_serializer_class(self):
        # Dynamically switch the serializer
        if self.action == 'create':
            return FeedbackWriteSerializer
        return FeedbackReadSerializer

    def get_permissions(self):
        # Security: Who is allowed to do what?
        if self.action == 'create':
            # Anyone logged in (specifically students) can POST
            return [permissions.IsAuthenticated()]
        
        # Only Admins/Staff can GET the list of all feedback
        return [permissions.IsAdminUser()]

    def perform_create(self, serializer):
        # Security: Extract the student from the auth token
        try:
            student = Student.objects.get(user=self.request.user)
            serializer.save(student=student)
        except Student.DoesNotExist:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Only registered students can submit feedback.")