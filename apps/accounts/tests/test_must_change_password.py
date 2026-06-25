"""First-login forced password change (must_change_password flag)."""

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase

User = get_user_model()
PW = "StrongP@ss9"


def make_user(email="user@college.edu", password=PW, **extra):
    return User.objects.create_user(email=email, password=password, **extra)


class MustChangePasswordDefaultTests(TestCase):
    def test_default_false(self):
        user = make_user()
        self.assertFalse(user.must_change_password)


class MustChangePasswordFlowTests(APITestCase):
    def setUp(self):
        self.user = make_user(email="temp@college.edu", password=PW)
        self.user.must_change_password = True
        self.user.save(update_fields=["must_change_password"])
        self.login_url = reverse("accounts:login")
        self.cp_url = reverse("accounts:change-password")

    def _login(self, password=PW):
        return self.client.post(
            self.login_url, {"email": "temp@college.edu", "password": password}, format="json"
        )

    def test_login_returns_flag(self):
        res = self._login()
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data["data"]["must_change_password"])

    def test_password_change_clears_flag(self):
        access = self._login().data["data"]["tokens"]["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        # request body is only {old_password, new_password} — confirm is optional
        res = self.client.post(
            self.cp_url, {"old_password": PW, "new_password": "NewP@ssw0rd1"}, format="json"
        )
        self.assertEqual(res.status_code, 200, res.data)
        self.user.refresh_from_db()
        self.assertFalse(self.user.must_change_password)
        # subsequent login reflects the cleared flag
        self.client.credentials()
        again = self._login(password="NewP@ssw0rd1")
        self.assertFalse(again.data["data"]["must_change_password"])

    def test_wrong_old_password_rejected(self):
        access = self._login().data["data"]["tokens"]["access"]
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access}")
        res = self.client.post(
            self.cp_url, {"old_password": "WrongP@ss9", "new_password": "NewP@ssw0rd1"}, format="json"
        )
        self.assertEqual(res.status_code, 400)
        self.user.refresh_from_db()
        self.assertTrue(self.user.must_change_password)  # unchanged on failure
