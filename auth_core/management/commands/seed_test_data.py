# auth_core/management/commands/seed_test_data.py
"""
Dev/test data seeder — creates one complete user per role and all the
related model rows needed to exercise every API endpoint.

Usage:
    python manage.py seed_test_data

Safe to run multiple times — uses get_or_create everywhere.

Credentials created:
    Role        | username      | password
    ------------|---------------|-------------
    super_admin | superadmin    | superadmin@123
    admin       | admin         | admin@123
    teacher     | teacher1      | teacher@123
    student     | student1      | student@123   (re-uses user pk=3 if exists)
"""

import datetime
from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.utils import timezone

User = get_user_model()


def _ok(label):   print(f'  [OK]      {label}')
def _skip(label): print(f'  [EXISTS]  {label}')
def _create(label, created):
    if created: _ok(label)
    else:        _skip(label)


class Command(BaseCommand):
    help = 'Seeds complete test data for all roles (student / teacher / admin / super_admin).'

    def handle(self, *args, **options):
        from users.models import Role, UserRole
        from students.models import Student, Teacher
        from academics.models import Faculty, Routine, ExamRoutine, Result
        from subjects.models import Subject
        from attendance.models import Attendance
        from fees.models import FeeStructure, StudentFee
        from feedback.models import Feedback
        from notices.models import Notice
        from auth_core.models import UserProfile

        self.stdout.write(self.style.SUCCESS('\n=== CMS Test Data Seeder ===\n'))

        # ── 1. Users ──────────────────────────────────────────────────────────
        self.stdout.write('[1/8] Creating users...')

        def make_user(username, email, first, last, password, is_superuser=False):
            user, created = User.objects.get_or_create(
                username=username,
                defaults={'email': email, 'first_name': first, 'last_name': last,
                          'is_superuser': is_superuser, 'is_staff': is_superuser},
            )
            user.set_password(password)
            user.save(update_fields=['password'])
            UserProfile.objects.get_or_create(user=user)
            label = f'User: {username} / {password}'
            _create(label, created)
            return user

        super_admin_user = make_user('superadmin', 'superadmin@college.com', 'Super',   'Admin',   'superadmin@123', is_superuser=True)
        admin_user       = make_user('admin',       'admin@college.com',      'Admin',   'User',    'admin@123')
        teacher_user     = make_user('teacher1',    'teacher1@college.com',   'Raj',     'Kumar',   'teacher@123')
        student_user     = make_user('student1',    'student1@college.com',   'Abhaya',  'Kunwar',  'student@123')

        # ── 2. Roles & UserRoles ──────────────────────────────────────────────
        self.stdout.write('\n[2/8] Assigning roles...')

        def assign_role(user, role_name):
            role = Role.objects.get(name=role_name)
            ur, created = UserRole.objects.get_or_create(user=user, defaults={'role': role})
            if not created and ur.role.name != role_name:
                ur.role = role; ur.save()
            _create(f'UserRole: {user.username} → {role_name}', created)

        assign_role(super_admin_user, 'super_admin')
        assign_role(admin_user,       'admin')
        assign_role(teacher_user,     'teacher')
        assign_role(student_user,     'student')

        # Auto-fix any OTHER users with no role (e.g. 'abhaya' pk=1)
        roled_user_ids = set(UserRole.objects.values_list('user_id', flat=True))
        orphans = User.objects.filter(is_active=True, is_superuser=False).exclude(pk__in=roled_user_ids)
        default_role = Role.objects.get(name='admin')
        for orphan in orphans:
            UserRole.objects.create(user=orphan, role=default_role)
            _ok(f'Auto-fixed orphan: {orphan.username} (pk={orphan.pk}) → admin')

        # ── 3. Teacher & Student profile rows ────────────────────────────────
        self.stdout.write('\n[3/8] Creating Student & Teacher profiles...')

        teacher, created = Teacher.objects.get_or_create(
            user=teacher_user,
            defaults={'department': 'Computer Science'},
        )
        _create(f'Teacher: {teacher_user.username} | dept={teacher.department}', created)

        try:
            student = Student.objects.get(user=student_user)
            _skip(f'Student: {student_user.username} | roll={student.roll_no}')
        except Student.DoesNotExist:
            # Find a free roll_no — S001 may already be taken by another user
            base, counter = 'S', 1
            while True:
                roll_no = f'{base}{counter:03d}'
                if not Student.objects.filter(roll_no=roll_no).exists():
                    break
                counter += 1
            student = Student.objects.create(
                user=student_user, roll_no=roll_no,
                course='BCA', year=1, section='A',
            )
            _ok(f'Student: {student_user.username} | roll={student.roll_no}')


        # ── 4. Academic structure (Faculty → Subject → Routine → ExamRoutine) ─
        self.stdout.write('\n[4/8] Creating academic structure...')

        faculty, created = Faculty.objects.get_or_create(name='Computer Science Faculty')
        _create(f'Faculty: {faculty.name}', created)

        subject, created = Subject.objects.get_or_create(
            code='CS101',
            defaults={
                'name':       'Introduction to Programming',
                'faculty':    faculty,
                'teacher':    teacher,
                'full_marks': 100,
                'pass_marks': 40,
            },
        )
        if not created and subject.teacher != teacher:
            subject.teacher = teacher
            subject.save(update_fields=['teacher'])
        _create(f'Subject: {subject.code} | {subject.name} | teacher={teacher_user.username}', created)

        # Class routine — Monday 09:00-10:00, Room 101
        routine, created = Routine.objects.get_or_create(
            room='101',
            day_of_week=Routine.Day.MONDAY,
            start_time=datetime.time(9, 0),
            defaults={
                'subject':    subject,
                'section':    'A',
                'end_time':   datetime.time(10, 0),
                'is_active':  True,
            },
        )
        _create(f'Routine: {subject.code} | Monday 09:00-10:00 | Room 101', created)

        # Exam routine — Final, 2026-06-15
        exam_date = datetime.date(2026, 6, 15)
        exam, created = ExamRoutine.objects.get_or_create(
            subject=subject,
            exam_type=ExamRoutine.ExamType.FINAL,
            exam_date=exam_date,
            defaults={
                'start_time': datetime.time(10, 0),
                'end_time':   datetime.time(13, 0),
                'room':       'Exam Hall A',
                'full_marks': 100,
                'pass_marks': 40,
                'notes':      'Bring your admit card.',
            },
        )
        _create(f'ExamRoutine: {subject.code} | Final | {exam_date}', created)

        # ── 5. Attendance ─────────────────────────────────────────────────────
        self.stdout.write('\n[5/8] Creating attendance record...')

        today = timezone.now().date()
        att, created = Attendance.objects.get_or_create(
            student=student,
            subject=subject,
            date=today,
            defaults={'status': 'present', 'marked_by': teacher_user},
        )
        _create(f'Attendance: {student.roll_no} | {subject.code} | {today} | {att.status}', created)

        # ── 6. Result ─────────────────────────────────────────────────────────
        self.stdout.write('\n[6/8] Creating result...')

        result, created = Result.objects.get_or_create(
            student=student_user,
            exam_routine=exam,
            defaults={
                'marks_obtained': Decimal('78.00'),
                'grade':          'B+',
                'is_published':   True,
                'is_deleted':     False,
                'remarks':        'Good performance.',
            },
        )
        _create(f'Result: {student_user.username} | {subject.code} | {result.marks_obtained}/{exam.full_marks} | {result.grade}', created)

        # ── 7. Fees ───────────────────────────────────────────────────────────
        self.stdout.write('\n[7/8] Creating fee structure & student fee...')

        fee_structure, created = FeeStructure.objects.get_or_create(
            faculty=faculty,
            year=1,
            semester=1,
            defaults={
                'tuition_fee':       Decimal('50000.00'),
                'exam_fee':          Decimal('5000.00'),
                'library_fee':       Decimal('2000.00'),
                'miscellaneous_fee': Decimal('1000.00'),
            },
        )
        _create(f'FeeStructure: {faculty.name} | Y1 S1 | Total={fee_structure.total}', created)

        student_fee, created = StudentFee.objects.get_or_create(
            student=student,
            fee_structure=fee_structure,
            defaults={
                'total_amount': fee_structure.total,
                'amount_paid':  Decimal('0.00'),
                'status':       StudentFee.Status.PENDING,
            },
        )
        _create(f'StudentFee: {student.roll_no} | {student_fee.status} | Due={student_fee.total_amount}', created)

        # ── 8. Feedback & Notices ─────────────────────────────────────────────
        self.stdout.write('\n[8/8] Creating feedback & notices...')

        feedback, created = Feedback.objects.get_or_create(
            student=student,
            target_teacher=teacher_user,
            type='feedback',
            defaults={'message': 'The lectures are very clear and well-structured.'},
        )
        _create(f'Feedback: {student.roll_no} → {teacher_user.username} | {feedback.type}', created)

        for title, notice_type, audience, priority in [
            ('Welcome to the New Semester',   'general',   'all',      'medium'),
            ('Final Exam Schedule Released',  'exam',      'students', 'high'),
            ('Fee Submission Deadline',       'fee',       'students', 'urgent'),
            ('Staff Meeting — Friday 3PM',    'general',   'teachers', 'medium'),
        ]:
            n, created = Notice.objects.get_or_create(
                title=title,
                defaults={
                    'type':            notice_type,
                    'content':         f'This is a test notice: {title}.',
                    'target_audience': audience,
                    'priority':        priority,
                    'is_active':       True,
                },
            )
            _create(f'Notice: [{notice_type}] [{priority}] {title}', created)

        # ── Summary ───────────────────────────────────────────────────────────
        self.stdout.write(self.style.SUCCESS('''
=== Seeding Complete ===

Credentials:
  Role        | Username    | Password
  ------------|-------------|---------------
  super_admin | superadmin  | superadmin@123
  admin       | admin       | admin@123
  teacher     | teacher1    | teacher@123
  student     | student1    | student@123

All endpoints should now return populated data.
Run: python manage.py runserver
'''))
