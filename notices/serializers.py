# notices/serializers.py
from rest_framework import serializers
from .models import Notice


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
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Title cannot be blank.")
        if len(value) < 5:
            raise serializers.ValidationError(
                "Title is too short. Write something meaningful."
            )
        return value

    def validate_content(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Notice content cannot be blank.")
        return value

    # --- Object-level validation ------------------------------------------

    def validate(self, attrs):
        """
        Emergency notices must be sent to everyone — not a subset.
        A targeted emergency defeats the purpose.
        """
        notice_type     = attrs.get('type',            getattr(self.instance, 'type',            None))
        target_audience = attrs.get('target_audience', getattr(self.instance, 'target_audience', None))

        if (notice_type == Notice.Type.EMERGENCY
                and target_audience != Notice.Audience.ALL):
            raise serializers.ValidationError({
                'target_audience': (
                    "Emergency notices must target everyone (ALL). "
                    "Restrict the audience only for non-emergency types."
                )
            })
        return attrs

    def to_representation(self, instance):
        return NoticeReadSerializer(instance, context=self.context).data