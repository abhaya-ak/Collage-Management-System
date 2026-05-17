# attendance/serializers.py
from django.utils import timezone
from rest_framework import serializers

from .models import Attendance
from students.models import Teacher


# ===========================================================================
# WRITE — teacher marks attendance for one student
# ===========================================================================

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

    # --- Field-level -------------------------------------------------------

    def validate_date(self, value):
        if value > timezone.now().date():
            raise serializers.ValidationError(
                "Attendance cannot be marked for a future date."
            )
        return value

    # --- Object-level ------------------------------------------------------

    def validate(self, attrs):
        self._validate_no_duplicate(attrs)
        self._validate_teacher_owns_subject(attrs)
        return attrs

    def _validate_no_duplicate(self, attrs):
        """
        unique_together on the model gives a raw DB error.
        Re-implement here for a clean 400 with a readable message.
        """
        student = attrs.get('student', getattr(self.instance, 'student', None))
        subject = attrs.get('subject', getattr(self.instance, 'subject', None))
        date    = attrs.get('date',    getattr(self.instance, 'date',    None))

        qs = Attendance.objects.filter(
            student=student, subject=subject, date=date
        )
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)

        if qs.exists():
            raise serializers.ValidationError(
                f"Attendance for this student in '{subject}' "
                f"on {date} has already been marked. "
                "Use the update endpoint to correct it."
            )

    def _validate_teacher_owns_subject(self, attrs):
        """
        A teacher can only mark attendance for their own subjects.
        Prevents Teacher A from marking attendance for Teacher B's class.
        request.user is accessed via serializer context.
        """
        request = self.context.get('request')
        if not request:
            return  # skip if called outside HTTP context (e.g. tests, shell)

        subject = attrs.get('subject', getattr(self.instance, 'subject', None))
        if not subject:
            return

        try:
            teacher = Teacher.objects.get(user=request.user)
        except Teacher.DoesNotExist:
            raise serializers.ValidationError(
                "Only registered teachers can mark attendance."
            )

        if subject.teacher_id != teacher.pk:
            raise serializers.ValidationError({
                'subject': (
                    f"You are not the assigned teacher for '{subject.name}'. "
                    "You can only mark attendance for your own subjects."
                )
            })

    def to_representation(self, instance):
        return AttendanceReadSerializer(instance, context=self.context).data


# ===========================================================================
# WRITE — teacher marks attendance for entire class at once (bulk)
# ===========================================================================

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

    # --- Field-level -------------------------------------------------------

    def validate_date(self, value):
        if value > timezone.now().date():
            raise serializers.ValidationError(
                "Attendance cannot be marked for a future date."
            )
        return value

    def validate_records(self, records):
        if not records:
            raise serializers.ValidationError(
                "Records list cannot be empty."
            )
        # Check for duplicate students in the same batch
        student_ids = [r['student'].pk for r in records]
        if len(student_ids) != len(set(student_ids)):
            raise serializers.ValidationError(
                "Duplicate students found in the records list. "
                "Each student must appear exactly once per batch."
            )
        return records

    # --- Object-level ------------------------------------------------------

    def validate(self, attrs):
        request = self.context.get('request')
        subject = attrs.get('subject')

        if request and subject:
            try:
                teacher = Teacher.objects.get(user=request.user)
            except Teacher.DoesNotExist:
                raise serializers.ValidationError(
                    "Only registered teachers can mark attendance."
                )
            if subject.teacher_id != teacher.pk:
                raise serializers.ValidationError({
                    'subject': (
                        f"You are not the assigned teacher for '{subject.name}'."
                    )
                })
        return attrs

    def save(self, **kwargs):
        """
        Upsert strategy — update_or_create per record.
        Safe to re-run if teacher corrects a mistake.
        Returns list of Attendance instances.
        """
        request   = self.context.get('request')
        subject   = self.validated_data['subject']
        date      = self.validated_data['date']
        records   = self.validated_data['records']
        marked_by = request.user if request else None

        results = []
        for row in records:
            obj, _ = Attendance.objects.update_or_create(
                student = row['student'],
                subject = subject,
                date    = date,
                defaults={
                    'status':    row['status'],
                    'marked_by': marked_by,
                },
            )
            results.append(obj)
        return results


# ===========================================================================
# READ — student views their own attendance report
# ===========================================================================

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


# ===========================================================================
# READ — admin views full attendance with student details
# ===========================================================================

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