# College Management System (CMS)

## Project Overview

The College Management System (CMS) is a production-grade web application designed for a single college. The system manages students, faculty, academics, attendance, examinations, fees, notifications, and reporting through role-based portals.

The system must be scalable, maintainable, secure, and follow software engineering best practices.

---

# Technology Stack

## Backend

* Python 3.13+
* Django 5+
* Django REST Framework
* PostgreSQL
* JWT Authentication
* RBAC Authorization

## Frontend

* React
* TypeScript
* Vite
* React Query
* React Hook Form

---

# User Roles

1. Super Admin
2. Admin
3. Teacher
4. Accountant
5. Student

---

# Core Modules

## Accounts

Responsible for:

* Authentication
* Authorization
* User Management
* Roles
* Permissions
* Audit Logs

## Academics

Responsible for:

* Academic Years
* Programs
* Semesters
* Subjects
* Sections

## Students

Responsible for:

* Student Profiles
* Admissions
* Enrollments
* Documents
* Student Dashboard

## Faculty

Responsible for:

* Faculty Profiles
* Subject Assignments
* Section Assignments
* Leave Requests

## Attendance

Responsible for:

* Attendance Sessions
* Attendance Records

## Exams

Responsible for:

* Exams
* Exam Schedules
* Marks
* Results
* Grade Scales

## Fees

Responsible for:

* Fee Structures
* Student Fees
* Payments
* Receipts

## Notifications

Responsible for:

* Notices
* Notifications
* Read Tracking

---

# Student Journey

Registration
→ Admission Approval
→ Enrollment
→ Attendance
→ Examinations
→ Results
→ Semester Completion

Student Portal Features:

* Dashboard
* Profile
* Attendance
* Results
* Fees
* Notices

---

# Teacher Journey

Faculty Creation
→ Subject Assignment
→ Attendance Management
→ Marks Entry

Teacher Portal Features:

* Dashboard
* Assigned Subjects
* Attendance
* Marks Entry
* Leave Requests

---

# Accountant Journey

Fee Structure Setup
→ Student Fee Assignment
→ Payment Collection
→ Receipt Generation

Accountant Portal Features:

* Dashboard
* Collect Fees
* Payment History
* Reports

---

# Admin Journey

Academic Setup
→ Student Admission
→ Faculty Assignment
→ Exam Creation
→ Result Publication

Admin Portal Features:

* Dashboard
* Students
* Faculty
* Academics
* Attendance
* Exams
* Finance
* Reports

---

# Database Design

Apps:

accounts
academics
students
faculty
attendance
exams
fees
notifications
core

Total Models: Approximately 35

Important Relationship:

Student
→ StudentEnrollment
→ AcademicYear
→ Program
→ Semester
→ Section

Faculty
→ FacultyAssignment
→ Subject
→ Section

Exam
→ ExamSchedule
→ Mark
→ Result

StudentFee
→ Payment
→ Receipt

---

# Engineering Requirements

All models must:

* Use UUID primary keys
* Include created_at
* Include updated_at
* Include soft delete support

API Requirements:

* RESTful APIs
* JWT Authentication
* Role-based permissions
* Pagination
* Filtering
* Search support

Performance Requirements:

* Use select_related where possible
* Use prefetch_related where necessary
* Add indexes on foreign keys
* Avoid N+1 queries

Security Requirements:

* RBAC Enforcement
* Audit Logging
* Permission Middleware
* Input Validation

---

# Coding Standards

* Clean Architecture
* Service Layer Pattern
* Repository Pattern where appropriate
* Typed serializers
* Modular apps
* Reusable permission classes

---

# Development Priority

1. Accounts
2. Academics
3. Students
4. Faculty
5. Attendance
6. Exams
7. Fees
8. Notifications
9. Dashboards
10. Reports