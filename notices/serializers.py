# notices/serializers.py
from rest_framework import serializers
from .models import Notice
from .services import NoticeService


# ---------------------------------------------------------------------------
# Read — what any authenticated user sees
# ---------------------------------------------------------------------------

class NoticeReadSerializer(serializers.ModelSerializer):
    """
    Clean card for the frontend notice board.
    Human labels instead of raw choice codes.
    """
    type_display            = serializers.CharField(
                                source='get_type_display',
                                read_only=True,
                              )
    target_audience_display = serializers.CharField(
                                source='get_target_audience_display',
                                read_only=True,
                              )

    class Meta:
        model  = Notice
        fields = [
            'id',
            'title',
            'type',            'type_display',
            'target_audience', 'target_audience_display',
            'content',
            'date_posted',
            'is_active',
        ]
        read_only_fields = fields


# ---------------------------------------------------------------------------
# Write — admin creates or updates a notice
# ---------------------------------------------------------------------------

class NoticeWriteSerializer(serializers.ModelSerializer):
    """
    Admin posts this. date_posted is auto-set by the DB — never accepted from input.
    Returns the full read representation on success.
    """

    class Meta:
        model  = Notice
        fields = [
            'id',
            'title',
            'type',
            'target_audience',
            'content',
            'is_active',
        ]
        read_only_fields = ['id']

    # --- Field-level validation -------------------------------------------

    def validate_title(self, value):
        try:
            return NoticeService.validate_title(value)
        except ValueError as e:
            raise serializers.ValidationError(str(e))

    def validate_content(self, value):
        try:
            return NoticeService.validate_content(value)
        except ValueError as e:
            raise serializers.ValidationError(str(e))

    def validate(self, attrs):
        notice_type     = attrs.get('type',            getattr(self.instance, 'type',            None))
        target_audience = attrs.get('target_audience', getattr(self.instance, 'target_audience', None))
        try:
            NoticeService.validate_emergency_audience(notice_type, target_audience)
        except ValueError as e:
            raise serializers.ValidationError({'target_audience': str(e)})
        return attrs

    def to_representation(self, instance):
        return NoticeReadSerializer(instance, context=self.context).data