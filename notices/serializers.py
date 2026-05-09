from rest_framework import serializers
from .models import Notice

class NoticeSerializer(serializers.ModelSerializer):
    """
    Contract for GET and POST /api/v1/notices/
    """
    class Meta:
        model = Notice
        fields = ['id', 'title', 'content', 'date_posted', 'target_audience']
        # The database automatically generates this, so the frontend shouldn't send it.
        read_only_fields = ['date_posted']