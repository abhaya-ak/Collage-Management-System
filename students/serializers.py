from rest_framework import serializers
from .models import Student, Teacher, Subject, Routine, ExamRoutine, Result, LeaveRequest

class StudentProfileSerializer(serializers.ModelSerializer):
    # Pulling specific fields from the related User model
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name = serializers.CharField(source='user.last_name', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)

    class Meta:
        model = Student
        # Explicitly defining exactly what the frontend profile screen needs
        fields = ['id', 'first_name', 'last_name', 'email', 'roll_no', 'course', 'year', 'section']

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