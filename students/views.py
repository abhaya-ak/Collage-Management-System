from rest_framework import viewsets, permissions
from .models import Student, Routine, Result, LeaveRequest
from .serializers import (
    StudentProfileSerializer, 
    RoutineSerializer, 
    ResultSerializer, 
    LeaveRequestSerializer
)

class StudentProfileViewSet(viewsets.ReadOnlyModelViewSet):
    """GET /students/ -> Lists students | GET /students/{id}/ -> Gets profile"""
    queryset = Student.objects.all()
    serializer_class = StudentProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

class RoutineViewSet(viewsets.ReadOnlyModelViewSet):
    """GET /routines/ -> Lists all routines"""
    queryset = Routine.objects.all()
    serializer_class = RoutineSerializer
    permission_classes = [permissions.IsAuthenticated]

class StudentResultViewSet(viewsets.ReadOnlyModelViewSet):
    """GET /results/ -> Lists ONLY the results for the logged-in student"""
    serializer_class = ResultSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Security: Only return results that belong to the user making the request
        return Result.objects.filter(student__user=self.request.user)

class LeaveRequestViewSet(viewsets.ModelViewSet):
    """GET /leaves/ -> List leaves | POST /leaves/ -> Create leave request"""
    serializer_class = LeaveRequestSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Security: Students can only see their own leave requests
        return LeaveRequest.objects.filter(student__user=self.request.user)

    def perform_create(self, serializer):
        # Automatically attach the logged-in student to the leave request
        student = Student.objects.get(user=self.request.user)
        serializer.save(student=student)