# users/models.py
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.conf import settings

class User(AbstractUser):
    pass

class Role(models.Model):
    name = models.CharField(max_length=50, unique=True)

    def __str__(self):
        return self.name


class Permission(models.Model):
    code   = models.CharField(max_length=100, unique=True)
    name   = models.CharField(max_length=100, default='', help_text="Human-readable label, e.g. 'View Results'")
    module = models.CharField(max_length=50,  default='', help_text="App this permission belongs to, e.g. 'academics'")

    def __str__(self):
        return f"{self.module} | {self.name} ({self.code})"


class RolePermission(models.Model):
    role       = models.ForeignKey(Role, on_delete=models.CASCADE)
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE)

    class Meta:
        unique_together = ("role", "permission")  # prevents duplicate assignments

class UserRole(models.Model):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    role = models.ForeignKey(Role, on_delete=models.CASCADE)