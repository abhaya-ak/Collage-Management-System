# attendance/serializers.py
from django.utils import timezone
from rest_framework import serializers
from .models import Attendance
from students.models import Teacher
from .services import AttendanceService

class AttendanceWriteSerializer(serializers.ModelSerializer):
    """
    Teacher posts this per student.
    'marked_by' excluded — set from auth token in view.
    Validates: no future dates, no duplicate record for same slot.
    """

    class Meta:
        model  = Attendance
        fields = ['id', 'student', 'subject', 'date', 'status']
        read_only_fields = ['id']

    def validate_date(self, value):
        try:
            AttendanceService.validate_date_not_future(value)
        except ValueError as e:
            raise serializers.ValidationError(str(e))
        return value

    def validate(self, attrs):
        def _get(f):
            return attrs.get(f, getattr(self.instance, f, None))
        request = self.context.get('request')
        try:
            AttendanceService.validate_no_duplicate(
                _get('student'), _get('subject'), _get('date'),
                exclude_pk=self.instance.pk if self.instance else None,
            )
            if request:
                AttendanceService.validate_teacher_owns_subject(request.user, _get('subject'))
        except ValueError as e:
            raise serializers.ValidationError(str(e))
        return attrs

    def to_representation(self, instance):
        return AttendanceReadSerializer(instance, context=self.context).data

class AttendanceBulkEntrySerializer(serializers.Serializer):
    """
    One row in a bulk submission — student + status only.
    Subject and date are shared across the whole batch (set at the list level).
    """
    student = serializers.PrimaryKeyRelatedField(
        queryset=__import__(
            'students.models', fromlist=['Student']
        ).Student.objects.all()
    )
    status  = serializers.ChoiceField(choices=Attendance.Status.choices)

class AttendanceBulkWriteSerializer(serializers.Serializer):
    """
    Teacher marks attendance for a full class in one POST.
    Payload:
    {
        "subject": 3,
        "date": "2026-05-17",
        "records": [
            {"student": 1, "status": "present"},
            {"student": 2, "status": "absent"},
            ...
        ]
    }
    Returns list of created/updated Attendance objects.
    """
    from subjects.models import Subject as _Subject
    from students.models import Student as _Student

    subject = serializers.PrimaryKeyRelatedField(
        queryset=_Subject.objects.all()
    )
    date    = serializers.DateField()
    records = AttendanceBulkEntrySerializer(many=True)

    def validate_date(self, value):
        try:
            AttendanceService.validate_date_not_future(value)
        except ValueError as e:
            raise serializers.ValidationError(str(e))
        return value

    def validate_records(self, records):
        try:
            AttendanceService.validate_bulk_records(records)
        except ValueError as e:
            raise serializers.ValidationError(str(e))
        return records

    def validate(self, attrs):
        request = self.context.get('request')
        subject = attrs.get('subject')
        if request and subject:
            try:
                AttendanceService.validate_teacher_owns_subject(request.user, subject)
            except ValueError as e:
                raise serializers.ValidationError(str(e))
        return attrs

    def save(self, **kwargs):
        request   = self.context.get('request')
        marked_by = request.user if request else None
        try:
            return AttendanceService.bulk_mark(
                subject   = self.validated_data['subject'],
                date      = self.validated_data['date'],
                records   = self.validated_data['records'],
                marked_by = marked_by,
            )
        except ValueError as e:
            raise serializers.ValidationError(str(e))

class AttendanceReadSerializer(serializers.ModelSerializer):
    """
    Student's attendance record card.
    Resolves all FKs to human labels — no raw IDs sent to frontend.
    """
    subject_name   = serializers.CharField(
        source='subject.name', read_only=True
    )
    subject_code   = serializers.CharField(
        source='subject.code', read_only=True
    )
    status_display = serializers.CharField(
        source='get_status_display', read_only=True
    )
    marked_by_name = serializers.SerializerMethodField()

    class Meta:
        model  = Attendance
        fields = [
            'id',
            'subject_name', 'subject_code',
            'date',
            'status', 'status_display',
            'marked_by_name',
            'created_at',
        ]
        read_only_fields = fields

    def get_marked_by_name(self, obj):
        if not obj.marked_by:
            return None
        u = obj.marked_by
        return f"{u.first_name} {u.last_name}".strip() or u.username

class AttendanceAdminReadSerializer(serializers.ModelSerializer):
    """
    Admin dashboard — full picture per record.
    """
    student_name   = serializers.SerializerMethodField()
    student_roll   = serializers.CharField(
        source='student.roll_no', read_only=True
    )
    subject_name   = serializers.CharField(
        source='subject.name', read_only=True
    )
    subject_code   = serializers.CharField(
        source='subject.code', read_only=True
    )
    status_display = serializers.CharField(
        source='get_status_display', read_only=True
    )
    marked_by_name = serializers.SerializerMethodField()

    class Meta:
        model  = Attendance
        fields = [
            'id',
            'student', 'student_name', 'student_roll',
            'subject', 'subject_name', 'subject_code',
            'date',
            'status', 'status_display',
            'marked_by', 'marked_by_name',
            'created_at',
        ]
        read_only_fields = fields

    def get_student_name(self, obj):
        u = obj.student.user
        return f"{u.first_name} {u.last_name}".strip()

    def get_marked_by_name(self, obj):
        if not obj.marked_by:
            return None
        u = obj.marked_by
        return f"{u.first_name} {u.last_name}".strip() or u.username