import tempfile
import unittest
from pathlib import Path

import app as dashboard_app


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        dashboard_app.DB_PATH = Path(self.temp_dir.name) / "test.db"
        dashboard_app.app.config.update(TESTING=True, SECRET_KEY="test-secret")
        dashboard_app.init_db()
        self.client = dashboard_app.app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def register(self):
        return self.client.post(
            "/register",
            data={
                "name": "Test Student",
                "email": "student@example.com",
                "password": "secure123",
            },
            follow_redirects=True,
        )

    def test_home_redirects_to_login(self):
        response = self.client.get("/", follow_redirects=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Welcome back", response.data)

    def test_registration_login_and_logout(self):
        response = self.register()
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Student Success Dashboard", response.data)

        response = self.client.get("/logout", follow_redirects=True)
        self.assertIn(b"Welcome back", response.data)

        response = self.client.post(
            "/login",
            data={"email": "student@example.com", "password": "secure123"},
            follow_redirects=True,
        )
        self.assertIn(b"Student Success Dashboard", response.data)

    def test_course_assignment_and_grade_average(self):
        self.register()
        self.client.post(
            "/courses/add",
            data={"name": "Computer Science", "code": "COMP 163", "target_grade": "90"},
        )

        with dashboard_app.get_db() as conn:
            course_id = conn.execute(
                "SELECT id FROM courses WHERE code = ?", ("COMP 163",)
            ).fetchone()["id"]

        response = self.client.post(
            "/assignments/add",
            data={
                "course_id": str(course_id),
                "title": "Python Project",
                "due_date": "2026-09-30",
                "score": "92",
                "max_score": "100",
                "weight": "1",
                "completed": "on",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"Python Project", response.data)
        self.assertIn(b"92.0%", response.data)

    def test_grade_forecast(self):
        self.register()
        response = self.client.post(
            "/forecast",
            data={
                "current_grade": "80",
                "target_grade": "85",
                "completed_weight": "50",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"90.0%", response.data)


if __name__ == "__main__":
    unittest.main()
