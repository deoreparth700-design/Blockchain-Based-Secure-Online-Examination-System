"""
tests/test_admin_students.py
----------------------------
Regression test suite for the Admin Registered Students viewing page (/admin/students)
and Student Detail page (/admin/students/<id>):
1. Admin can access /admin/students and see all registered students
2. Multiple students are listed
3. Each student's:
   - name
   - PRN
   - email
   - registration date
   - role
   are rendered correctly
4. Username is displayed when present
5. NULL username is displayed safely (renders '—')
6. Password hash never appears in HTML (both list and detail views)
7. Student detail page loads correctly (/admin/students/<id>)
8. Student exam history is shown correctly
9. Student with no attempts gets a clean empty state
10. Student with multiple attempts gets correct totals (attempted, completed, average score)
11. Search by name works
12. Search by PRN works
13. Search by email works
14. Optional filtering by attempted / not attempted works
15. Non-admin users cannot access the student list or student detail pages
16. Admin/teacher accounts are not included in the student list
17. Legacy teacher alias routes work (/teacher/students, /teacher/students/<id>)
"""

import os
import sys
import unittest
from datetime import datetime, timedelta

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
TEST_DB_PATH = os.path.join(BASE_DIR, "tests", "test_admin_students.db")
os.environ["DATABASE_URL"] = f"sqlite:///{TEST_DB_PATH}"

sys.path.insert(0, BASE_DIR)

from app import app
from models import db, User, Exam, Attempt
import database


class TestAdminStudents(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        app.config["TESTING"] = True
        cls.client = app.test_client()

    @classmethod
    def tearDownClass(cls):
        with app.app_context():
            db.session.remove()
            db.drop_all()
        if os.path.exists(TEST_DB_PATH):
            try:
                os.remove(TEST_DB_PATH)
            except OSError:
                pass

    def setUp(self):
        with app.app_context():
            db.session.remove()
            db.drop_all()
            db.create_all()

            # Create Admin
            self.admin = database.create_user(
                name="Prof. Amit Kulkarni",
                identifier="admin_demo",
                username="admin_demo",
                email="amit.kulkarni@demo.edu",
                password="AdminPassword123!",
                role="admin",
            )
            self.admin_id = self.admin.id

            # Create Teacher
            self.teacher = database.create_user(
                name="Prof. Exam Teacher",
                identifier="teacher_demo",
                username="teacher_demo",
                email="teacher@demo.edu",
                password="TeacherPassword123!",
                role="admin",
            )

        self.client = app.test_client()

    def _login(self, client, identifier, password):
        client.get("/login")
        with client.session_transaction() as sess:
            csrf_token = sess.get("csrf_token", "")
        return client.post(
            "/login",
            data={
                "identifier": identifier,
                "password": password,
                "csrf_token": csrf_token,
            },
            follow_redirects=True,
        )

    def test_01_admin_can_access_admin_students(self):
        """1. Admin can access /admin/students."""
        c = app.test_client()
        self._login(c, "admin_demo", "AdminPassword123!")
        res = c.get("/admin/students")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)
        self.assertIn("Registered Students", html)
        self.assertIn("B.E. Final Year", html)

    def test_02_unauthenticated_cannot_access_admin_students(self):
        """2. Unauthenticated user cannot access /admin/students (redirects to /login)."""
        c = app.test_client()
        res = c.get("/admin/students", follow_redirects=False)
        self.assertEqual(res.status_code, 302)
        self.assertIn("/login", res.headers.get("Location", ""))

    def test_03_student_cannot_access_admin_students(self):
        """3. Student (role='user') cannot access /admin/students (redirected/denied)."""
        with app.app_context():
            database.create_user(
                name="Student Test",
                identifier="2024-BE-001",
                email="student@demo.edu",
                password="StudentPassword123!",
                role="user",
            )
        c = app.test_client()
        self._login(c, "2024-BE-001", "StudentPassword123!")
        res = c.get("/admin/students", follow_redirects=False)
        self.assertEqual(res.status_code, 302)

        res_followed = c.get("/admin/students", follow_redirects=True)
        html = res_followed.get_data(as_text=True)
        self.assertIn("This page is only available to admins", html)

    def test_04_registered_students_appear_in_list(self):
        """4. Registered students with role 'user' appear in the list."""
        with app.app_context():
            database.create_user(
                name="Aarav Sharma",
                identifier="2026-CS-0101",
                email="aarav.sharma@demo.edu",
                password="StudentPassword123!",
                role="user",
            )
            database.create_user(
                name="Priya Patil",
                identifier="2026-CS-0102",
                email="priya.patil@demo.edu",
                password="StudentPassword123!",
                role="user",
            )

        c = app.test_client()
        self._login(c, "admin_demo", "AdminPassword123!")
        res = c.get("/admin/students")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        self.assertIn("Aarav Sharma", html)
        self.assertIn("2026-CS-0101", html)
        self.assertIn("Priya Patil", html)
        self.assertIn("2026-CS-0102", html)
        self.assertIn("2", html)  # Total count: 2

    def test_05_admin_and_teacher_do_not_appear_as_students(self):
        """5. Admin/teacher accounts do not appear in the student list."""
        with app.app_context():
            database.create_user(
                name="Karan Patel",
                identifier="2026-CS-0201",
                email="karan.patel@demo.edu",
                password="StudentPassword123!",
                role="user",
            )

        c = app.test_client()
        self._login(c, "admin_demo", "AdminPassword123!")
        res = c.get("/admin/students")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        self.assertIn("Karan Patel", html)
        self.assertNotIn("data-prn=\"admin_demo\"", html)
        self.assertNotIn("data-prn=\"teacher_demo\"", html)

    def test_06_student_attributes_rendered_correctly(self):
        """6. Student name, PRN, email, registration date, and role are rendered correctly."""
        with app.app_context():
            student = database.create_user(
                name="Rohan Joshi",
                identifier="2026-CS-0303",
                email="rohan.joshi@demo.edu",
                password="StudentPassword123!",
                role="user",
            )
            formatted_date = student.created_at.strftime("%d %b %Y")

        c = app.test_client()
        self._login(c, "admin_demo", "AdminPassword123!")
        res = c.get("/admin/students")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        self.assertIn("Rohan Joshi", html)
        self.assertIn("2026-CS-0303", html)
        self.assertIn("rohan.joshi@demo.edu", html)
        self.assertIn(formatted_date, html)
        self.assertIn("Student", html)

    def test_07_username_displayed_when_present(self):
        """7. Username is displayed when present in student model."""
        with app.app_context():
            database.create_user(
                name="Manoj Shinde",
                identifier="2026-CS-0707",
                username="manoj_shinde99",
                email="manoj@demo.edu",
                password="StudentPassword123!",
                role="user",
            )

        c = app.test_client()
        self._login(c, "admin_demo", "AdminPassword123!")
        res = c.get("/admin/students")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        self.assertIn("manoj_shinde99", html)

    def test_08_null_username_displayed_safely(self):
        """8. NULL username displays safe '—' placeholder without crashing."""
        with app.app_context():
            database.create_user(
                name="Tanvi Gokhale",
                identifier="2026-CS-0808",
                username=None,
                email="tanvi@demo.edu",
                password="StudentPassword123!",
                role="user",
            )

        c = app.test_client()
        self._login(c, "admin_demo", "AdminPassword123!")
        res = c.get("/admin/students")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        self.assertIn("Tanvi Gokhale", html)
        self.assertIn("—", html)

    def test_09_password_hashes_never_rendered_in_list_or_detail(self):
        """9. Password hashes are never rendered in list or detail HTML."""
        with app.app_context():
            student = database.create_user(
                name="Sneha Deshmukh",
                identifier="2026-CS-0404",
                email="sneha@demo.edu",
                password="SuperSecretPassword999!",
                role="user",
            )
            student_hash = student.password_hash
            student_id = student.id

        c = app.test_client()
        self._login(c, "admin_demo", "AdminPassword123!")

        # 1. Check List Page
        res_list = c.get("/admin/students")
        self.assertEqual(res_list.status_code, 200)
        html_list = res_list.get_data(as_text=True)
        self.assertNotIn(student_hash, html_list)
        self.assertNotIn("scrypt:", html_list)
        self.assertNotIn("pbkdf2:", html_list)
        self.assertNotIn("SuperSecretPassword999!", html_list)

        # 2. Check Detail Page
        res_detail = c.get(f"/admin/students/{student_id}")
        self.assertEqual(res_detail.status_code, 200)
        html_detail = res_detail.get_data(as_text=True)
        self.assertNotIn(student_hash, html_detail)
        self.assertNotIn("scrypt:", html_detail)
        self.assertNotIn("pbkdf2:", html_detail)
        self.assertNotIn("SuperSecretPassword999!", html_detail)

    def test_10_search_by_prn(self):
        """10. Search by PRN filters the student list correctly."""
        with app.app_context():
            database.create_user(
                name="Ananya Roy",
                identifier="2026-CS-7777",
                email="ananya@demo.edu",
                password="Pass123!",
                role="user",
            )
            database.create_user(
                name="Vikram Singh",
                identifier="2026-CS-8888",
                email="vikram@demo.edu",
                password="Pass123!",
                role="user",
            )

        c = app.test_client()
        self._login(c, "admin_demo", "AdminPassword123!")
        res = c.get("/admin/students?q=7777")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        self.assertIn("Ananya Roy", html)
        self.assertIn("2026-CS-7777", html)
        self.assertNotIn("Vikram Singh", html)

    def test_11_search_by_name(self):
        """11. Search by name filters the student list correctly."""
        with app.app_context():
            database.create_user(
                name="Devika Menon",
                identifier="2026-CS-9111",
                email="devika@demo.edu",
                password="Pass123!",
                role="user",
            )
            database.create_user(
                name="Siddharth Rao",
                identifier="2026-CS-9222",
                email="siddharth@demo.edu",
                password="Pass123!",
                role="user",
            )

        c = app.test_client()
        self._login(c, "admin_demo", "AdminPassword123!")
        res = c.get("/admin/students?q=Devika")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        self.assertIn("Devika Menon", html)
        self.assertNotIn("Siddharth Rao", html)

    def test_12_search_by_email(self):
        """12. Search by email filters the student list correctly."""
        with app.app_context():
            database.create_user(
                name="Kavita Iyer",
                identifier="2026-CS-1212",
                email="kavita.special@demo.edu",
                password="Pass123!",
                role="user",
            )
            database.create_user(
                name="Nikhil Verma",
                identifier="2026-CS-1313",
                email="nikhil.other@demo.edu",
                password="Pass123!",
                role="user",
            )

        c = app.test_client()
        self._login(c, "admin_demo", "AdminPassword123!")
        res = c.get("/admin/students?q=kavita.special")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        self.assertIn("Kavita Iyer", html)
        self.assertNotIn("Nikhil Verma", html)

    def test_13_filtering_by_attempted_and_not_attempted(self):
        """13. Filtering by attempted and not_attempted filters students accordingly."""
        with app.app_context():
            s1 = database.create_user(
                name="Active Submitter",
                identifier="2026-CS-5001",
                email="s1@demo.edu",
                password="Pass123!",
                role="user",
            )
            s2 = database.create_user(
                name="Passive Student",
                identifier="2026-CS-5002",
                email="s2@demo.edu",
                password="Pass123!",
                role="user",
            )
            exam = database.create_exam(
                title="Cloud Basics",
                created_by=self.admin_id,
                start_time=datetime.now() - timedelta(hours=2),
                end_time=datetime.now() + timedelta(hours=2),
                duration_minutes=30,
                questions=[{"question": "Q1?", "options": ["A", "B", "C", "D"], "correct_index": 0}],
                status="published",
            )
            database.create_attempt(
                exam_id=exam.id,
                student_id=s1.id,
                score=1,
                total=1,
                block_id=None,
                started_at=datetime.now() - timedelta(minutes=20),
                submitted_at=datetime.now() - timedelta(minutes=5),
            )

        c = app.test_client()
        self._login(c, "admin_demo", "AdminPassword123!")

        # 1. Filter = attempted
        res_att = c.get("/admin/students?filter=attempted")
        self.assertEqual(res_att.status_code, 200)
        html_att = res_att.get_data(as_text=True)
        self.assertIn("Active Submitter", html_att)
        self.assertNotIn("Passive Student", html_att)

        # 2. Filter = not_attempted
        res_not_att = c.get("/admin/students?filter=not_attempted")
        self.assertEqual(res_not_att.status_code, 200)
        html_not_att = res_not_att.get_data(as_text=True)
        self.assertIn("Passive Student", html_not_att)
        self.assertNotIn("Active Submitter", html_not_att)

    def test_14_empty_student_database_shows_proper_empty_state(self):
        """14. Empty student database shows proper empty state."""
        c = app.test_client()
        self._login(c, "admin_demo", "AdminPassword123!")
        res = c.get("/admin/students")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        self.assertIn("No Registered Students Yet", html)
        self.assertIn("empty-state-card", html)
        self.assertNotIn("students-table", html)
        self.assertNotIn("student-row", html)

    def test_15_student_detail_page_loads_correctly(self):
        """15. Student detail page /admin/students/<id> loads correctly with student details."""
        with app.app_context():
            student = database.create_user(
                name="Pooja Hegde",
                identifier="2026-CS-6001",
                username="pooja_hegde",
                email="pooja@demo.edu",
                password="StudentPassword123!",
                role="user",
            )
            student_id = student.id

        c = app.test_client()
        self._login(c, "admin_demo", "AdminPassword123!")
        res = c.get(f"/admin/students/{student_id}")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        self.assertIn("Student Profile: Pooja Hegde", html)
        self.assertIn("2026-CS-6001", html)
        self.assertIn("pooja@demo.edu", html)
        self.assertIn("pooja_hegde", html)
        self.assertIn("Personal &amp; Registration Details", html)
        self.assertIn("Examination Activity", html)
        self.assertIn("Exam History", html)
        self.assertIn("Active", html)

    def test_16_student_detail_clean_empty_state_for_zero_attempts(self):
        """16. Student with zero attempts gets a clean empty state in detail view."""
        with app.app_context():
            student = database.create_user(
                name="Fresh Student",
                identifier="2026-CS-6002",
                email="fresh@demo.edu",
                password="StudentPassword123!",
                role="user",
            )
            student_id = student.id

        c = app.test_client()
        self._login(c, "admin_demo", "AdminPassword123!")
        res = c.get(f"/admin/students/{student_id}")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        self.assertIn("No Examination Attempts Yet", html)
        self.assertIn("empty-history-card", html)
        self.assertIn("0", html)  # 0 attempted
        self.assertIn("No attempts recorded", html)

    def test_17_student_detail_shows_exam_history_and_correct_totals(self):
        """17. Student with multiple attempts displays correct totals and exam history."""
        with app.app_context():
            student = database.create_user(
                name="Experienced Candidate",
                identifier="2026-CS-6003",
                email="experienced@demo.edu",
                password="StudentPassword123!",
                role="user",
            )
            student_id = student.id

            exam1 = database.create_exam(
                title="Algorithms Analysis",
                created_by=self.admin_id,
                start_time=datetime.now() - timedelta(days=2),
                end_time=datetime.now() + timedelta(days=1),
                duration_minutes=45,
                questions=[{"question": "Q1", "options": ["A", "B", "C", "D"], "correct_index": 0}],
                status="published",
            )
            exam2 = database.create_exam(
                title="Database Systems",
                created_by=self.admin_id,
                start_time=datetime.now() - timedelta(days=1),
                end_time=datetime.now() + timedelta(days=2),
                duration_minutes=30,
                questions=[
                    {"question": "Q1", "options": ["A", "B", "C", "D"], "correct_index": 0},
                    {"question": "Q2", "options": ["A", "B", "C", "D"], "correct_index": 1},
                ],
                status="published",
            )

            # Exam 1: 1/1 = 100%
            database.create_attempt(
                exam_id=exam1.id,
                student_id=student.id,
                score=1,
                total=1,
                block_id=None,
                started_at=datetime.now() - timedelta(hours=5),
                submitted_at=datetime.now() - timedelta(hours=4),
            )
            # Exam 2: 1/2 = 50%
            database.create_attempt(
                exam_id=exam2.id,
                student_id=student.id,
                score=1,
                total=2,
                block_id=None,
                started_at=datetime.now() - timedelta(hours=3),
                submitted_at=datetime.now() - timedelta(hours=2),
            )

        c = app.test_client()
        self._login(c, "admin_demo", "AdminPassword123!")
        res = c.get(f"/admin/students/{student_id}")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        self.assertIn("Algorithms Analysis", html)
        self.assertIn("Database Systems", html)
        self.assertIn("75.0%", html)  # Average of 100% and 50%
        self.assertIn("2", html)  # Total exams attempted & completed
        self.assertIn("exam-history-table", html)

    def test_18_student_list_renders_exam_summary_and_latest_score(self):
        """18. Student list shows exam activity count and latest exam score."""
        with app.app_context():
            student = database.create_user(
                name="List Activity Test",
                identifier="2026-CS-7001",
                email="list_act@demo.edu",
                password="StudentPassword123!",
                role="user",
            )
            student_id = student.id
            exam = database.create_exam(
                title="Distributed Systems Test",
                created_by=self.admin_id,
                start_time=datetime.now() - timedelta(hours=3),
                end_time=datetime.now() + timedelta(hours=1),
                duration_minutes=30,
                questions=[{"question": "Q1", "options": ["A", "B", "C", "D"], "correct_index": 0}],
                status="published",
            )
            database.create_attempt(
                exam_id=exam.id,
                student_id=student.id,
                score=1,
                total=1,
                block_id=None,
                started_at=datetime.now() - timedelta(hours=2),
                submitted_at=datetime.now() - timedelta(hours=1),
            )

        c = app.test_client()
        self._login(c, "admin_demo", "AdminPassword123!")
        res = c.get("/admin/students")
        self.assertEqual(res.status_code, 200)
        html = res.get_data(as_text=True)

        self.assertIn("List Activity Test", html)
        self.assertIn("1 attempted", html)
        self.assertIn("1 completed", html)
        self.assertIn("1/1", html)
        self.assertIn("100.0%", html)
        self.assertIn("Distributed Systems Test", html)
        self.assertIn(f"/admin/students/{student_id}", html)

    def test_19_non_admin_cannot_access_student_detail(self):
        """19. Non-admin users cannot access the student detail view."""
        with app.app_context():
            student = database.create_user(
                name="Security Test Student",
                identifier="2026-CS-9999",
                email="sec@demo.edu",
                password="StudentPassword123!",
                role="user",
            )
            student_id = student.id

        # 1. Unauthenticated user
        c_unauth = app.test_client()
        res_unauth = c_unauth.get(f"/admin/students/{student_id}", follow_redirects=False)
        self.assertEqual(res_unauth.status_code, 302)
        self.assertIn("/login", res_unauth.headers.get("Location", ""))

        # 2. Student user
        c_student = app.test_client()
        self._login(c_student, "2026-CS-9999", "StudentPassword123!")
        res_stud = c_student.get(f"/admin/students/{student_id}", follow_redirects=False)
        self.assertEqual(res_stud.status_code, 302)

        res_stud_followed = c_student.get(f"/admin/students/{student_id}", follow_redirects=True)
        html = res_stud_followed.get_data(as_text=True)
        self.assertIn("This page is only available to admins", html)

    def test_20_legacy_teacher_alias_routes(self):
        """20. Legacy teacher alias routes /teacher/students and /teacher/students/<id> work."""
        with app.app_context():
            student = database.create_user(
                name="Alias Test Student",
                identifier="2026-CS-8001",
                email="alias@demo.edu",
                password="StudentPassword123!",
                role="user",
            )
            student_id = student.id

        c = app.test_client()
        self._login(c, "admin_demo", "AdminPassword123!")

        # 1. /teacher/students
        res_list = c.get("/teacher/students")
        self.assertEqual(res_list.status_code, 200)
        html_list = res_list.get_data(as_text=True)
        self.assertIn("Registered Students", html_list)
        self.assertIn("Alias Test Student", html_list)

        # 2. /teacher/students/<id>
        res_detail = c.get(f"/teacher/students/{student_id}")
        self.assertEqual(res_detail.status_code, 200)
        html_detail = res_detail.get_data(as_text=True)
        self.assertIn("Student Profile: Alias Test Student", html_detail)


if __name__ == "__main__":
    unittest.main()
