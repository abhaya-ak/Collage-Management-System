# dashboard/serializers.py
from rest_framework import serializers


class StudentStatsSerializer(serializers.Serializer):
    total = serializers.IntegerField()


class AttendanceStatsSerializer(serializers.Serializer):
    today_marked    = serializers.IntegerField()
    overall_avg_pct = serializers.CharField(
        help_text="Aggregate attendance % across all records (LATE=PRESENT policy). String-encoded Decimal."
    )


class FeeStatsSerializer(serializers.Serializer):
    total_billed    = serializers.CharField(help_text="Sum of all StudentFee.total_amount")
    total_collected = serializers.CharField(help_text="Sum of all StudentFee.amount_paid")
    outstanding     = serializers.CharField(help_text="total_billed - total_collected")
    pending_bills   = serializers.IntegerField()
    partial_bills   = serializers.IntegerField()
    paid_bills      = serializers.IntegerField()


class FeedbackStatsSerializer(serializers.Serializer):
    total    = serializers.IntegerField()
    pending  = serializers.IntegerField()
    reviewed = serializers.IntegerField()
    resolved = serializers.IntegerField()
    closed   = serializers.IntegerField()


class NoticeStatsSerializer(serializers.Serializer):
    active   = serializers.IntegerField()
    inactive = serializers.IntegerField()
    urgent   = serializers.IntegerField()


class DashboardOverviewSerializer(serializers.Serializer):
    """
    Top-level admin dashboard overview.
    All monetary values are string-encoded Decimals.
    """
    students   = StudentStatsSerializer()
    attendance = AttendanceStatsSerializer()
    fees       = FeeStatsSerializer()
    feedback   = FeedbackStatsSerializer()
    notices    = NoticeStatsSerializer()
