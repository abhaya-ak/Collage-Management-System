# users/views.py

from django.contrib.auth import get_user_model
from rest_framework import viewsets, status, serializers
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework.response import Response

from auth_core.permissions import HasPermission, IsAdminRole
from auth_core.services.rbac_service import RBACService
from users.constants import PermissionCodes, RoleNames
from users.models import Role, UserRole

User = get_user_model()


class RoleSerializer(serializers.ModelSerializer):
    class Meta:
        model  = Role
        fields = ['id', 'name']


class UserListSerializer(serializers.ModelSerializer):
    """Read — user card shown to admins."""
    role = serializers.SerializerMethodField()

    class Meta:
        model  = User
        fields = [
            'id', 'username', 'email',
            'first_name', 'last_name',
            'is_active', 'date_joined', 'role',
        ]
        read_only_fields = fields

    def get_role(self, obj) -> str | None:
        return RBACService.get_role(obj)


class UserCreateSerializer(serializers.Serializer):
    """
    Admin creates a new user, assigns a role, and optionally creates the
    domain profile in one atomic request.

    Teacher fields (required when role='teacher'):
      department  — e.g. "Computer Science"

    Student fields (required when role='student'):
      roll_no, course, year, section
    """
    username   = serializers.CharField(max_length=150)
    email      = serializers.EmailField()
    password   = serializers.CharField(write_only=True, min_length=8,
                                       style={'input_type': 'password'})
    first_name = serializers.CharField(max_length=150, default='')
    last_name  = serializers.CharField(max_length=150, default='')
    role       = serializers.ChoiceField(choices=RoleNames.ALL, required=False,
                                         default=RoleNames.STUDENT)

    # ── Teacher profile fields ───────────────────────────────────────────────
    department = serializers.CharField(max_length=100, required=False, default='')

    # ── Student profile fields ───────────────────────────────────────────────
    roll_no = serializers.CharField(max_length=50,  required=False, default='')
    course  = serializers.CharField(max_length=100, required=False, default='')
    year    = serializers.IntegerField(required=False, default=1, min_value=1)
    section = serializers.CharField(max_length=10,  required=False, default='')

    def validate_username(self, value):
        if User.objects.filter(username__iexact=value).exists():
            raise serializers.ValidationError('This username is already taken.')
        return value.strip()

    def validate_email(self, value):
        value = value.strip().lower()
        if User.objects.filter(email__iexact=value).exists():
            raise serializers.ValidationError('An account with this email already exists.')
        return value

    def validate_role(self, value):
        if not Role.objects.filter(name=value).exists():
            raise serializers.ValidationError(
                f"Role '{value}' does not exist. Run `python manage.py seed_roles` first."
            )
        return value

    def validate(self, attrs):
        """Cross-field validation: enforce required profile fields per role."""
        role = attrs.get('role', RoleNames.STUDENT)

        if role == RoleNames.TEACHER:
            if not attrs.get('department', '').strip():
                raise serializers.ValidationError(
                    {'department': 'This field is required when role is "teacher".'}
                )

        if role == RoleNames.STUDENT:
            errors = {}
            if not attrs.get('roll_no', '').strip():
                errors['roll_no'] = 'Required when role is "student".'
            if not attrs.get('course', '').strip():
                errors['course'] = 'Required when role is "student".'
            if not attrs.get('section', '').strip():
                errors['section'] = 'Required when role is "student".'
            if errors:
                raise serializers.ValidationError(errors)

            # roll_no uniqueness check
            from students.models import Student
            if Student.objects.filter(roll_no=attrs['roll_no']).exists():
                raise serializers.ValidationError(
                    {'roll_no': f"Roll number '{attrs['roll_no']}' is already taken."}
                )

        return attrs


class UserRoleChangeSerializer(serializers.Serializer):
    """Body for PATCH /api/v1/users/{id}/role/"""
    role = serializers.ChoiceField(choices=RoleNames.ALL)

    def validate_role(self, value):
        if not Role.objects.filter(name=value).exists():
            raise serializers.ValidationError(
                f"Role '{value}' does not exist. Run `python manage.py seed_roles` first."
            )
        return value


class UserViewSet(viewsets.GenericViewSet):
    """
    GET    /api/v1/users/                list all users          (USERS_VIEW_ALL)
    POST   /api/v1/users/                create user + role      (USERS_MANAGE)
    GET    /api/v1/users/{id}/           detail                  (USERS_VIEW_ALL)
    PATCH  /api/v1/users/{id}/role/      change role             (USERS_MANAGE)
    DELETE /api/v1/users/{id}/           deactivate (soft)       (USERS_MANAGE)
    """
    permission_classes  = [HasPermission]
    required_permission = PermissionCodes.USERS_VIEW_ALL
    filter_backends     = [SearchFilter, OrderingFilter]
    search_fields       = ['username', 'email', 'first_name', 'last_name']
    ordering_fields     = ['username', 'date_joined', 'email']
    ordering            = ['username']

    def get_queryset(self):
        return (
            User.objects
            .select_related('userrole', 'userrole__role')
            .order_by('username')
        )

    # ── LIST ─────────────────────────────────────────────────────────────────

    def list(self, request):
        """GET /api/v1/users/"""
        qs = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(qs)
        if page is not None:
            return self.get_paginated_response(
                UserListSerializer(page, many=True).data
            )
        return Response(UserListSerializer(qs, many=True).data)

    # ── RETRIEVE ─────────────────────────────────────────────────────────────

    def retrieve(self, request, pk=None):
        """GET /api/v1/users/{id}/"""
        user = self._get_user_or_404(pk)
        return Response(UserListSerializer(user).data)
        
    def create(self, request):
        """
        POST /api/v1/users/
        Creates user + role + domain profile in one atomic transaction.
        Teacher: pass 'department'.
        Student: pass 'roll_no', 'course', 'year', 'section'.
        """
        self._require_manage()
        serializer = UserCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        from django.db import transaction
        from auth_core.models import UserProfile
        from auth_core.services.password_reset_service import PasswordResetService
        from students.models import Student, Teacher

        with transaction.atomic():
            # 1. Create the auth user
            user = User.objects.create_user(
                username   = d['username'],
                email      = d['email'],
                password   = d['password'],
                first_name = d.get('first_name', ''),
                last_name  = d.get('last_name', ''),
            )

            # 2. UserProfile (avatar, phone, bio)
            UserProfile.objects.get_or_create(user=user)

            # 3. Role assignment — signal fires here
            role_name = d.get('role', RoleNames.STUDENT)
            role      = Role.objects.get(name=role_name)
            UserRole.objects.create(user=user, role=role)

            # 4. Domain profile — explicit creation overrides signal default
            if role_name == RoleNames.TEACHER:
                # Signal may have created with 'Unassigned'; update with real dept
                Teacher.objects.update_or_create(
                    user=user,
                    defaults={'department': d['department'].strip()},
                )

            elif role_name == RoleNames.STUDENT:
                Student.objects.create(
                    user    = user,
                    roll_no = d['roll_no'].strip(),
                    course  = d['course'].strip(),
                    year    = d['year'],
                    section = d['section'].strip(),
                )

        # Send welcome email OUTSIDE the transaction — a transient SMTP failure
        # must never roll back the created account.  The admin can resend via the
        # forgot-password flow if the email is lost.
        PasswordResetService.send_welcome_email(user, request)

        return Response(
            UserListSerializer(user).data,
            status=status.HTTP_201_CREATED,
        )


    # ── ROLE CHANGE ───────────────────────────────────────────────────────────

    @action(detail=True, methods=['patch'], url_path='role',
            permission_classes=[IsAdminRole])
    def change_role(self, request, pk=None):
        """
        PATCH /api/v1/users/{id}/role/
        Body: {"role": "teacher"}
        Atomically replaces the user's current role assignment.
        """
        user = self._get_user_or_404(pk)

        serializer = UserRoleChangeSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        role_name = serializer.validated_data['role']

        from django.db import transaction
        with transaction.atomic():
            role = Role.objects.get(name=role_name)
            UserRole.objects.update_or_create(
                user=user,
                defaults={'role': role},
            )
            # Invalidate cached RBAC permissions for this user
            cache_attr = f'_rbac_perms_{user.pk}'
            if hasattr(user, cache_attr):
                delattr(user, cache_attr)

        return Response(UserListSerializer(user).data, status=status.HTTP_200_OK)

    # ── DEACTIVATE (soft delete) ──────────────────────────────────────────────

    def destroy(self, request, pk=None):
        """
        DELETE /api/v1/users/{id}/
        Sets is_active=False — never hard-deletes the account.
        Returns 204 on success.
        """
        self._require_manage()
        user = self._get_user_or_404(pk)

        if user == request.user:
            return Response(
                {'detail': 'You cannot deactivate your own account.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        if user.is_superuser:
            return Response(
                {'detail': 'Superuser accounts cannot be deactivated via the API.'},
                status=status.HTTP_403_FORBIDDEN,
            )

        user.is_active = False
        user.save(update_fields=['is_active'])
        return Response(status=status.HTTP_204_NO_CONTENT)

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _get_user_or_404(self, pk):
        try:
            return self.get_queryset().get(pk=pk)
        except User.DoesNotExist:
            from rest_framework.exceptions import NotFound
            raise NotFound(f'User {pk} not found.')

    def _require_manage(self):
        """Raises PermissionDenied if caller lacks USERS_MANAGE."""
        user = self.request.user
        if not (user.is_superuser or RBACService.has_permission(user, PermissionCodes.USERS_MANAGE)):
            raise PermissionDenied('You do not have permission to manage users.')
