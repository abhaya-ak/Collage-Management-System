from rest_framework import serializers
from .models import Student, Subject, Routine, Result, LeaveRequest
from .models import Routine
from attendance.models import Attendance
from notices.models import Notice
from feedback.models import Feedback

class StudentProfileSerializer(serializers.ModelSerializer):
    # Pulling specific fields from the related User model
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = Student
        # Explicitly defining exactly what the frontend profile screen needs
        fields = ['id', 'first_name', 'last_name', 'email', 'roll_no', 'course', 'year', 'section']

'''class StudentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Student
        fields = ['id', 'first_name', 'last_name', 'email']'''

class SubjectSerializer(serializers.ModelSerializer):
    class Meta:
        model = Subject
        fields = ['id', 'name', 'course']

class RoutineSerializer(serializers.ModelSerializer):
    # Nesting the subject so the frontend gets the subject name, not just an ID
    subject = SubjectSerializer(read_only=True)

    class Meta:
        model = Routine
        fields = ['id', 'subject', 'day', 'start_time', 'end_time']

class ResultSerializer(serializers.ModelSerializer):
    subject_name = serializers.CharField(source='subject.name', read_only=True)

    class Meta:
        model = Result
        fields = ['id', 'subject_name', 'marks', 'grade']

class LeaveRequestSerializer(serializers.ModelSerializer):
    class Meta:
        model = LeaveRequest
        # We DO NOT include the 'student' field here. 
        # We will automatically set the student in the view based on the logged-in user.
        fields = ['id', 'from_date', 'to_date', 'reason', 'approved']
        read_only_fields = ['approved'] # Students cannot approve their own leaves!

class TeacherRoutineSerializer(serializers.ModelSerializer):
    # Teachers need to see the subject name and course, not just the ID
    subject_name = serializers.CharField(source='subject.name', read_only=True)
    course = serializers.CharField(source='subject.course', read_only=True)

    class Meta:
        model = Routine
        fields = ['id', 'subject_name', 'course', 'day', 'start_time', 'end_time']

class MarkAttendanceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Attendance
        # Notice we do NOT include 'marked_by' here. The API must never trust the frontend 
        # to say who is marking attendance. We will extract that from the auth token in the View.
        fields = ['id', 'student', 'subject', 'date', 'status']

class NoticeSerializer(serializers.ModelSerializer):
    class Meta:
        model = Notice
        fields = ['id', 'title', 'content', 'date_posted', 'target_audience']

class TeacherFeedbackSerializer(serializers.ModelSerializer):
    # Get the student's name so the teacher knows who submitted it
    student_name = serializers.SerializerMethodField()

    class Meta:
        model = Feedback
        fields = ['id', 'student_name', 'subject', 'message', 'submitted_at']
        
    def get_student_name(self, obj):
        return f"{obj.student.user.first_name} {obj.student.user.last_name}"