from rest_framework import viewsets, permissions
from .models import Student, LeaveRequest
from academics.models import Routine
from attendance.models import Attendance
from notices.models import Notice
from feedback.models import Feedback

from .serializers import (
    StudentProfileSerializer, 
    RoutineSerializer, 
    ResultSerializer, 
    LeaveRequestSerializer, 
    TeacherRoutineSerializer, 
    MarkAttendanceSerializer, 
    NoticeSerializer, 
    TeacherFeedbackSerializer
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
        return 'academics.Result'.objects.filter(student__user=self.request.user)

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


class TeacherRoutineViewSet(viewsets.ReadOnlyModelViewSet):
    """GET /teacher-routines/ -> Lists routines only for the logged-in teacher"""
    serializer_class = TeacherRoutineSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Security: Find the teacher profile of the logged-in user, 
        # then return only routines linked to subjects taught by them.
        return Routine.objects.filter(subject__teacher__user=self.request.user)

class AttendanceViewSet(viewsets.ModelViewSet):
    """POST /attendance/ -> Mark attendance"""
    serializer_class = MarkAttendanceSerializer
    permission_classes = [permissions.IsAuthenticated]
    queryset = Attendance.objects.all()

    def perform_create(self, serializer):
        # Security Rule: Automatically attach the logged-in teacher as the 'marked_by' person.
        # This prevents Teacher A from forging attendance as Teacher B.
        teacher = Teacher.objects.get(user=self.request.user)
        serializer.save(marked_by=teacher)

class NoticeViewSet(viewsets.ReadOnlyModelViewSet):
    """GET /notices/ -> List notices"""
    serializer_class = NoticeSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Teachers should only see notices meant for 'ALL' or 'TEACHERS'
        return Notice.objects.filter(target_audience__in=['ALL', 'TEACHERS']).order_by('-date_posted')

class TeacherFeedbackViewSet(viewsets.ReadOnlyModelViewSet):
    """GET /feedback/ -> View feedback directed at this teacher"""
    serializer_class = TeacherFeedbackSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Security: Teachers can only read feedback explicitly targeted at them
        return Feedback.objects.filter(target_teacher__user=self.request.user).order_by('-submitted_at')