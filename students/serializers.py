# students/serializers.py

from rest_framework import serializers
from django.utils import timezone
from .models import Student, Teacher, LeaveRequest
from .services import StudentService, LeaveRequestService

class StudentProfileSerializer(serializers.ModelSerializer):
    """
    READ-ONLY — profile screen payload.
    Flattens related User fields; frontend never sees the raw user ID.
    """
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name  = serializers.CharField(source='user.last_name',  read_only=True)
    email      = serializers.EmailField(source='user.email',     read_only=True)
    username   = serializers.CharField(source='user.username',   read_only=True)

    class Meta:
        model  = Student
        fields = [
            'id', 'username', 'first_name', 'last_name',
            'email', 'roll_no', 'course', 'year', 'section',
        ]
        read_only_fields = fields


class StudentWriteSerializer(serializers.ModelSerializer):
    """
    ADMIN ONLY — create or update a student record.
    Does NOT create the User — user must already exist.
    Returns the full read representation on success via to_representation().
    """
    class Meta:
        model  = Student
        fields = ['id', 'user', 'roll_no', 'course', 'year', 'section']
        read_only_fields = ['id']

    def validate_user(self, user):
        try:
            StudentService.validate_unique_profile(
                user, exclude_pk=self.instance.pk if self.instance else None
            )
        except ValueError as e:
            raise serializers.ValidationError(str(e))
        return user

    def validate_year(self, value):
        try:
            StudentService.validate_year(value)
        except ValueError as e:
            raise serializers.ValidationError(str(e))
        return value

    def to_representation(self, instance):
        """Always return the flattened read shape after a write."""
        return StudentProfileSerializer(instance, context=self.context).data


class TeacherSerializer(serializers.ModelSerializer):
    """
    READ-ONLY teacher card — used wherever teacher info is displayed.
    """
    full_name = serializers.SerializerMethodField()
    email     = serializers.EmailField(source='user.email',   read_only=True)
    username  = serializers.CharField(source='user.username', read_only=True)

    class Meta:
        model  = Teacher
        fields = ['id', 'username', 'full_name', 'email', 'department']
        read_only_fields = fields

    def get_full_name(self, obj):
        return f"{obj.user.first_name} {obj.user.last_name}".strip()


class LeaveRequestReadSerializer(serializers.ModelSerializer):
    """
    READ — what students and admins see when listing leave requests.
    Resolves student FK to a human name; exposes a readable status label.
    """
    student_name = serializers.SerializerMethodField()
    status       = serializers.SerializerMethodField()

    class Meta:
        model  = LeaveRequest
        fields = [
            'id', 'student_name',
            'from_date', 'to_date', 'reason',
            'approved', 'status',
        ]
        read_only_fields = fields

    def get_student_name(self, obj):
        u = obj.student.user
        return f"{u.first_name} {u.last_name}".strip()

    def get_status(self, obj):
        return "Approved" if obj.approved else "Pending"


class LeaveRequestWriteSerializer(serializers.ModelSerializer):
    """
    WRITE — students submit this.
    'student' is injected by the view from the auth token.
    'approved' is never accepted from input — admin sets it separately.
    Returns the read shape on success via to_representation().
    """
    class Meta:
        model  = LeaveRequest
        fields = ['id', 'from_date', 'to_date', 'reason', 'approved']
        read_only_fields = ['id', 'approved']

    # --- Field-level --------------------------------------------------------

    def validate_from_date(self, value):
        try:
            LeaveRequestService.validate_from_date_not_past(value)
        except ValueError as e:
            raise serializers.ValidationError(str(e))
        return value

    def validate(self, attrs):
        from_date = attrs.get('from_date', getattr(self.instance, 'from_date', None))
        to_date   = attrs.get('to_date',   getattr(self.instance, 'to_date',   None))
        try:
            LeaveRequestService.validate_date_range(from_date, to_date)
        except ValueError as e:
            raise serializers.ValidationError({'to_date': str(e)})
        return attrs

    def to_representation(self, instance):
        """Always return the read shape after a write."""
        return LeaveRequestReadSerializer(instance, context=self.context).data