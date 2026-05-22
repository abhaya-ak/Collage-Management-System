# auth_core/serializers.py
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from auth_core.models import UserProfile
from auth_core.services.rbac_service import RBACService

User = get_user_model()


class RegisterSerializer(serializers.Serializer):
    username   = serializers.CharField(max_length=150)
    email      = serializers.EmailField()
    password   = serializers.CharField(write_only=True, min_length=8, style={'input_type': 'password'})
    first_name = serializers.CharField(max_length=150)
    last_name  = serializers.CharField(max_length=150)

    def validate_username(self, value):
        value = value.strip()
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError('This username is already taken.')
        return value

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError('An account with this email already exists.')
        return value

    def validate_password(self, value):
        validate_password(value)
        return value


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True, style={'input_type': 'password'})


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True, style={'input_type': 'password'})
    new_password = serializers.CharField(write_only=True, min_length=8, style={'input_type': 'password'})

    def validate_new_password(self, value):
        validate_password(value)
        return value


class UserProfileSerializer(serializers.ModelSerializer):
    """
    Full profile view — wraps UserProfile + related User fields + RBAC data.
    Used by GET /api/v1/auth/me/
    """
    username   = serializers.CharField(source='user.username',   read_only=True)
    email      = serializers.EmailField(source='user.email',     read_only=True)
    first_name = serializers.CharField(source='user.first_name', read_only=True)
    last_name  = serializers.CharField(source='user.last_name',  read_only=True)
    role        = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()

    class Meta:
        model  = UserProfile
        fields = [
            'username', 'email', 'first_name', 'last_name',
            'avatar', 'phone', 'bio',
            'role', 'permissions',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'username', 'email', 'role', 'permissions',
            'created_at', 'updated_at',
        ]

    def get_role(self, obj) -> str | None:
        return RBACService.get_role(obj.user)

    def get_permissions(self, obj) -> list:
        # Exclude synthetic 'role:xxx' entries from the public response
        return sorted(
            p for p in RBACService.load_permissions(obj.user)
            if not p.startswith('role:')
        )
