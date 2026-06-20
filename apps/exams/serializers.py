"""Serializers for the exam/result domain."""

from rest_framework import serializers

from apps.academics.models import ProgramSemesterSubject
from apps.exams.models import Exam, ExamSchedule, Mark, Result, ResultItem
from apps.students.models import Student


# --- Exam -------------------------------------------------------------------
class ExamSerializer(serializers.ModelSerializer):
    class Meta:
        model = Exam
        fields = ["id", "name", "academic_year", "program", "semester",
                  "exam_type", "status", "start_date", "end_date", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate(self, attrs):
        start = attrs.get("start_date", getattr(self.instance, "start_date", None))
        end = attrs.get("end_date", getattr(self.instance, "end_date", None))
        if start and end and end < start:
            raise serializers.ValidationError({"end_date": "End date cannot be before start date."})
        return attrs


# --- ExamSchedule -----------------------------------------------------------
class ExamScheduleSerializer(serializers.ModelSerializer):
    subject_code = serializers.CharField(source="subject.code", read_only=True)
    section_name = serializers.CharField(source="section.name", read_only=True)

    class Meta:
        model = ExamSchedule
        fields = ["id", "exam", "subject", "subject_code", "section", "section_name",
                  "exam_date", "start_time", "end_time", "created_at"]
        read_only_fields = ["id", "subject_code", "section_name", "created_at"]

    def validate(self, attrs):
        exam = attrs.get("exam", getattr(self.instance, "exam", None))
        subject = attrs.get("subject", getattr(self.instance, "subject", None))
        section = attrs.get("section", getattr(self.instance, "section", None))
        if exam and section and (section.program_id != exam.program_id
                                 or section.semester_id != exam.semester_id):
            raise serializers.ValidationError(
                {"section": "Section does not belong to the exam's program/semester."}
            )
        if exam and subject and not ProgramSemesterSubject.objects.filter(
            program=exam.program, semester=exam.semester, subject=subject
        ).exists():
            raise serializers.ValidationError(
                {"subject": f"{subject.code} is not in the {exam.program.code} "
                            f"Semester {exam.semester.number} curriculum."}
            )
        return attrs


# --- Marks ------------------------------------------------------------------
class MarkEntrySerializer(serializers.Serializer):
    """Write payload for POST /marks/enter/. grade/grade_point/total are computed."""

    student = serializers.PrimaryKeyRelatedField(queryset=Student.objects.all())
    exam_schedule = serializers.PrimaryKeyRelatedField(queryset=ExamSchedule.objects.all())
    theory_marks = serializers.DecimalField(max_digits=5, decimal_places=2, required=False, allow_null=True)
    practical_marks = serializers.DecimalField(max_digits=5, decimal_places=2, required=False, allow_null=True)
    internal_marks = serializers.DecimalField(max_digits=5, decimal_places=2, required=False, allow_null=True)
    is_absent = serializers.BooleanField(required=False, default=False)


class MarkSerializer(serializers.ModelSerializer):
    student = serializers.CharField(source="student.student_id", read_only=True)
    subject = serializers.CharField(source="exam_schedule.subject.code", read_only=True)
    entered_by = serializers.CharField(source="entered_by.email", read_only=True, default=None)

    class Meta:
        model = Mark
        fields = ["id", "student", "subject", "theory_marks", "practical_marks",
                  "internal_marks", "total_marks", "grade", "grade_point",
                  "is_absent", "entered_by", "entered_at", "is_published"]
        read_only_fields = fields


# --- Results ----------------------------------------------------------------
class ResultItemSerializer(serializers.ModelSerializer):
    subject = serializers.CharField(source="subject.code", read_only=True)

    class Meta:
        model = ResultItem
        fields = ["id", "subject", "marks", "grade", "grade_point", "credits"]


class ResultSerializer(serializers.ModelSerializer):
    student = serializers.CharField(source="student.student_id", read_only=True)
    exam = serializers.CharField(source="exam.name", read_only=True)

    class Meta:
        model = Result
        fields = ["id", "student", "exam", "gpa", "cgpa", "total_credits",
                  "earned_credits", "published", "published_at", "generated_at"]
        read_only_fields = fields


class ResultDetailSerializer(ResultSerializer):
    items = ResultItemSerializer(many=True, read_only=True)

    class Meta(ResultSerializer.Meta):
        fields = ResultSerializer.Meta.fields + ["items"]


class GenerateResultSerializer(serializers.Serializer):
    student = serializers.PrimaryKeyRelatedField(queryset=Student.objects.all())
    exam = serializers.PrimaryKeyRelatedField(queryset=Exam.objects.all())
