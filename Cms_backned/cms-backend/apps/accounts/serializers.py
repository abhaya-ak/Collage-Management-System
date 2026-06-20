"""
Sprint 4 — Step 1: Auth serializers ONLY.
LoginSerializer, UserSerializer, ChangePasswordSerializer. Nothing else.
"""

from django.contrib.auth.password_validation import validate_password
from rest_framework import serializers

from apps.accounts.models import CustomUser


class LoginSerializer(serializers.Serializer):
    """Validates login input. Authentication happens in the service layer."""

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True, style={"input_type": "password"})


class CreateUserSerializer(serializers.Serializer):
    """POST /api/auth/users/ — superuser creates a user with roles."""

    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True, default="")
    phone_number = serializers.CharField(max_length=20, required=False, allow_blank=True, default="")
    roles = serializers.ListField(
        child=serializers.ChoiceField(choices=[
            ("SUPER_ADMIN", "Super Admin"), ("ADMIN", "Admin"), ("TEACHER", "Teacher"),
            ("ACCOUNTANT", "Accountant"), ("STUDENT", "Student"),
        ]),
        allow_empty=False,
    )

    def validate_password(self, value):
        validate_password(value)
        return value

    def validate_email(self, value):
        if CustomUser.all_objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value


class SetRolesSerializer(serializers.Serializer):
    """POST /api/auth/users/<id>/set-roles/ — superuser replaces a user's roles."""

    roles = serializers.ListField(
        child=serializers.ChoiceField(choices=[
            ("SUPER_ADMIN", "Super Admin"), ("ADMIN", "Admin"), ("TEACHER", "Teacher"),
            ("ACCOUNTANT", "Accountant"), ("STUDENT", "Student"),
        ]),
        allow_empty=False,
    )


class UserSerializer(serializers.ModelSerializer):
    """Read-only representation of the current user, incl. roles & permissions."""

    full_name = serializers.CharField(read_only=True)
    roles = serializers.SerializerMethodField()
    permissions = serializers.SerializerMethodField()
    profile_completion = serializers.SerializerMethodField()

    class Meta:
        model = CustomUser
        fields = [
            "id",
            "email",
            "username",
            "first_name",
            "last_name",
            "full_name",
            "phone_number",
            "profile_photo",
            "profile_completion",
            "is_active",
            "is_staff",
            "is_superuser",
            "roles",
            "permissions",
            "last_login",
            "created_at",
        ]
        read_only_fields = fields

    def get_roles(self, obj) -> list[str]:
        return sorted(obj.get_role_names())

    def get_permissions(self, obj) -> list[str]:
        return sorted(obj.get_permission_codes())

    def get_profile_completion(self, obj) -> int:
        """Percentage of profile fields filled (first/last name, phone, photo)."""
        fields = [obj.first_name, obj.last_name, obj.phone_number, obj.profile_photo]
        filled = sum(1 for f in fields if f)
        return round(filled / len(fields) * 100)


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True)
    confirm_password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        if attrs["new_password"] != attrs["confirm_password"]:
            raise serializers.ValidationError(
                {"confirm_password": "Passwords do not match."}
            )
        if attrs["old_password"] == attrs["new_password"]:
            raise serializers.ValidationError(
                {"new_password": "New password must be different from the old one."}
            )
        # Enforce Django's AUTH_PASSWORD_VALIDATORS.
        user = self.context.get("request").user if self.context.get("request") else None
        validate_password(attrs["new_password"], user)
        return attrs


class ProfileUpdateSerializer(serializers.ModelSerializer):
    """
    PATCH /api/auth/me/ — self-service profile fields only.
    Email, roles, and permissions cannot be changed here.
    """

    class Meta:
        model = CustomUser
        fields = ["first_name", "last_name", "phone_number", "profile_photo", "username"]
        extra_kwargs = {
            "first_name": {"required": False, "allow_blank": False},
            "last_name": {"required": False, "allow_blank": False},
            "phone_number": {"required": False, "allow_blank": False},
            "profile_photo": {"required": False},
            "username" : {"required": False}
        }