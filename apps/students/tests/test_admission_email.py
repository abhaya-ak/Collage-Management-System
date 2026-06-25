"""Auto-generated institutional login email during admission."""

from datetime import date
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core import mail
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.academics.models import AcademicYear, Program, Section, Semester
from apps.accounts.models import Role
from apps.core.enums import UserRole
from apps.students.models import Student
from apps.students.services import generate_account_email

User = get_user_model()


class GenerateAccountEmailTests(TestCase):
    def _user(self, email):
        return User.objects.create_user(email=email, password="StrongP@ss9")

    def test_generates_name_based_email(self):
        self.assertEqual(generate_account_email("Ram", "Sharma"), "ram.sharma@college.edu")

    def test_multiword_name_normalized(self):
        self.assertEqual(
            generate_account_email("Ram  Bahadur", "Sharma"),
            "ram.bahadur.sharma@college.edu",
        )

    def test_special_characters_stripped(self):
        self.assertEqual(generate_account_email("Jane!", "O'Doe"), "jane.odoe@college.edu")

    def test_duplicate_name_gets_incremented_suffix(self):
        self._user("ram.sharma@college.edu")
        self.assertEqual(generate_account_email("Ram", "Sharma"), "ram.sharma1@college.edu")
        self._user("ram.sharma1@college.edu")
        self.assertEqual(generate_account_email("Ram", "Sharma"), "ram.sharma2@college.edu")

    def test_soft_deleted_email_still_blocks_reuse(self):
        u = self._user("ram.sharma@college.edu")
        u.delete()  # soft delete
        # all_objects includes soft-deleted, so the email must NOT be reused.
        self.assertEqual(generate_account_email("Ram", "Sharma"), "ram.sharma1@college.edu")


class AdmissionEmailAPITests(APITestCase):
    def setUp(self):
        Role.objects.create(name=UserRole.STUDENT, description="Student")
        self.su = User.objects.create_superuser(email="admin@college.edu", password="Admin@123")
        self.client.force_authenticate(user=self.su)

        self.year = AcademicYear.objects.create(
            name="2026", start_date=date(2026, 1, 1), end_date=date(2026, 12, 31), is_current=True
        )
        self.program = Program.objects.create(
            code="BCA", name="BCA", duration_years=4, total_semesters=8
        )
        self.sem1 = Semester.objects.create(number=1, name="Semester 1")
        self.section = Section.objects.create(
            program=self.program, semester=self.sem1, name="A", capacity=30
        )
        self.url = reverse("students:student-admission")

    def _payload(self, **over):
        body = {
            "first_name": "Ram",
            "last_name": "Sharma",
            "gender": "MALE",
            "date_of_birth": "2005-03-02",
            "email": "ram.personal@gmail.com",
            "admission_date": "2026-01-10",
            "registration_number": "REG-2026-001",
            "program": str(self.program.id),
        }
        body.update(over)
        return body

    def test_admission_without_account_email(self):
        # No account_email in the request at all.
        res = self.client.post(self.url, self._payload(), format="json")
        self.assertEqual(res.status_code, 201, res.data)
        student = Student.objects.get(registration_number="REG-2026-001")
        self.assertEqual(student.user.email, "ram.sharma@college.edu")

    def test_credential_email_sent_on_admission(self):
        with self.captureOnCommitCallbacks(execute=True):
            res = self.client.post(self.url, self._payload(), format="json")
        self.assertEqual(res.status_code, 201, res.data)
        temp_pw = res.data["data"]["temporary_password"]

        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        self.assertEqual(email.subject, "Welcome to College")
        self.assertEqual(email.to, ["ram.personal@gmail.com"])   # personal email
        # credentials included correctly
        self.assertIn("ram.sharma@college.edu", email.body)       # login email
        self.assertIn(temp_pw, email.body)                        # temp password
        self.assertIn(res.data["data"]["student_id"], email.body)

    def test_admission_succeeds_if_email_fails(self):
        with patch(
            "django.core.mail.EmailMultiAlternatives.send", side_effect=Exception("smtp down")
        ):
            with self.captureOnCommitCallbacks(execute=True):
                res = self.client.post(self.url, self._payload(), format="json")
        # admission must still succeed even though the email send blew up
        self.assertEqual(res.status_code, 201, res.data)
        self.assertTrue(
            Student.objects.filter(registration_number="REG-2026-001").exists()
        )
        self.assertEqual(len(mail.outbox), 0)

    def test_resend_credentials_new_password_and_email(self):
        admit = self.client.post(self.url, self._payload(), format="json")
        student_pk = admit.data["data"]["id"]
        old_pw = admit.data["data"]["temporary_password"]
        mail.outbox.clear()

        with self.captureOnCommitCallbacks(execute=True):
            res = self.client.post(
                f"/api/students/{student_pk}/resend-credentials/", {}, format="json"
            )
        self.assertEqual(res.status_code, 200, res.data)
        new_pw = res.data["data"]["temporary_password"]
        self.assertNotEqual(new_pw, old_pw)                 # fresh password
        self.assertEqual(len(mail.outbox), 1)               # re-emailed
        self.assertIn("ram.sharma@college.edu", mail.outbox[0].body)

        # new password works; flag re-set
        student = Student.objects.get(pk=student_pk)
        self.assertTrue(student.user.must_change_password)
        self.client.force_authenticate(user=None)
        login = self.client.post(
            reverse("accounts:login"),
            {"email": "ram.sharma@college.edu", "password": new_pw}, format="json",
        )
        self.assertEqual(login.status_code, 200, login.data)

    def test_resend_credentials_forbidden_for_non_admin(self):
        admit = self.client.post(self.url, self._payload(), format="json")
        student_pk = admit.data["data"]["id"]
        nobody = User.objects.create_user(email="nobody@college.edu", password="StrongP@ss9")
        self.client.force_authenticate(user=nobody)
        res = self.client.post(
            f"/api/students/{student_pk}/resend-credentials/", {}, format="json"
        )
        self.assertEqual(res.status_code, 403)

    def test_admission_sets_must_change_password(self):
        res = self.client.post(self.url, self._payload(), format="json")
        self.assertEqual(res.status_code, 201, res.data)
        student = Student.objects.get(registration_number="REG-2026-001")
        self.assertTrue(student.user.must_change_password)

    def test_enrollment_date_defaults_to_admission_date(self):
        res = self.client.post(self.url, self._payload(), format="json")
        self.assertEqual(res.status_code, 201, res.data)
        student = Student.objects.get(registration_number="REG-2026-001")
        enrollment = student.enrollments.get()
        self.assertEqual(str(enrollment.enrollment_date), "2026-01-10")
        self.assertEqual(enrollment.enrollment_date, student.admission_date)

    def test_generated_email_returned_in_response(self):
        res = self.client.post(self.url, self._payload(), format="json")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertEqual(res.data["data"]["account_email"], "ram.sharma@college.edu")
        self.assertTrue(res.data["data"]["student_id"].startswith("STU-"))

    def test_duplicate_name_admission_increments_email(self):
        first = self.client.post(self.url, self._payload(), format="json")
        self.assertEqual(first.data["data"]["account_email"], "ram.sharma@college.edu")
        # second student, same name; different registration number AND contact email
        # (Student.email is unique; only the generated login email auto-increments)
        second = self.client.post(
            self.url,
            self._payload(registration_number="REG-2026-002", email="ram.alt@gmail.com"),
            format="json",
        )
        self.assertEqual(second.status_code, 201, second.data)
        self.assertEqual(second.data["data"]["account_email"], "ram.sharma1@college.edu")

    def test_admission_without_password(self):
        # No password in the request — system generates one.
        res = self.client.post(self.url, self._payload(), format="json")
        self.assertEqual(res.status_code, 201, res.data)
        self.assertIn("temporary_password", res.data["data"])
        self.assertTrue(res.data["data"]["temporary_password"])

    def test_temporary_password_works_for_login(self):
        res = self.client.post(self.url, self._payload(), format="json")
        email = res.data["data"]["account_email"]
        temp_pw = res.data["data"]["temporary_password"]
        # The generated credentials must actually authenticate.
        self.client.force_authenticate(user=None)
        login = self.client.post(
            reverse("accounts:login"),
            {"email": email, "password": temp_pw}, format="json",
        )
        self.assertEqual(login.status_code, 200, login.data)
        self.assertIn("access", login.data["data"]["tokens"])
