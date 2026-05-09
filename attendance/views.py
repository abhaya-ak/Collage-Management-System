from rest_framework import generics, permissions
from .models import Attendance, Teacher
from .serializers import AttendanceWriteSerializer, AttendanceReadSerializer

class MarkAttendanceAPIView(generics.CreateAPIView):
    """
    POST /api/v1/attendance/mark/
    """
    serializer_class = AttendanceWriteSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        # Security: The teacher marking attendance is pulled from the auth token
        # This guarantees a student can't hack the API and mark themselves present.
        try:
            teacher = Teacher.objects.get(user=self.request.user)
            serializer.save(marked_by=teacher)
        except Teacher.DoesNotExist:
            from rest_framework.exceptions import PermissionDenied
            raise PermissionDenied("Only teachers can mark attendance.")

class StudentAttendanceReportAPIView(generics.ListAPIView):
    """
    GET /api/v1/attendance/student/{id}/
    """
    serializer_class = AttendanceReadSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Extract the {id} from the URL
        student_id = self.kwargs.get('id')
        
        # Return all attendance records for that specific student, ordered newest first
        return Attendance.objects.filter(student_id=student_id).order_by('-date')