"""
Automatic tests for StudentTrack.
Run with:   python -m unittest test_app -v
The tests use a temporary database, so your real students.db is never touched.
"""
import os
import sys
import tempfile
import sqlite3
import unittest

PROJECT = os.path.dirname(os.path.abspath(__file__))
TEMP = tempfile.mkdtemp()
os.chdir(TEMP)                      # the app makes students.db in the current folder
sys.path.insert(0, PROJECT)
import app as A                     # noqa: E402


def text(response):
    return response.get_data(as_text=True)


class StudentTrackTests(unittest.TestCase):

    def setUp(self):
        if os.path.exists("students.db"):
            os.remove("students.db")
        A.make_table()
        self.c = A.app.test_client()

    # ----- helpers -----
    def signup(self, enrollment="E1", name="Ravi", mobile="9876543210", password="secret1"):
        return self.c.post("/signup", data={"username": name, "Father_name": "Mohan", "Enrollment": enrollment,
                                            "Mobile": mobile, "Gmail": "a@b.com", "password": password},
                           follow_redirects=True)

    def login(self, client=None, enrollment="E1", password="secret1"):
        client = client or self.c
        return client.post("/login", data={"enrollment": enrollment, "password": password})

    def student(self, enrollment="E1", name="Ravi"):
        self.signup(enrollment, name)
        self.login(enrollment=enrollment)

    def teacher(self, client=None, password="teacher123"):
        client = client or self.c
        return client.post("/teacher", data={"teacher_id": "teacher", "password": password})

    def db(self):
        return sqlite3.connect("students.db")

    def one(self, sql, args=()):
        return self.db().execute(sql, args).fetchone()

    def add_skill(self, name="Python", level="Beginner", progress="20"):
        return self.c.post("/addskill", data={"skill": name, "level": level, "category": "Programming",
                                              "progress": progress, "learning_note": ""})

    def record(self, subject="Maths", mid="25", end="60", internal="18", enrollment="E1"):
        return self.c.post("/teacher/record", data={"enrollment": enrollment, "subject": subject,
                                                    "mid_sem": mid, "end_sem": end, "internal_lab": internal})

    # ===== Login, sign up, logout =====
    def test_first_page_is_login_with_about_text(self):
        h = text(self.c.get("/"))
        self.assertIn("Create Account", h)
        self.assertIn("Teacher Login", h)
        self.assertNotIn("Get Started", h)

    def test_signup_and_login(self):
        self.assertIn("Account created", text(self.signup()))
        r = self.login()
        self.assertEqual(r.status_code, 302)
        self.assertTrue(r.headers["Location"].endswith("/dashboard"))

    def test_password_is_saved_hashed(self):
        self.signup()
        self.assertNotEqual(self.one("SELECT password FROM users")[0], "secret1")

    def test_signup_checks(self):
        self.assertIn("10 digits", text(self.signup(mobile="123")))
        self.assertIn("at least 6", text(self.signup(password="abc")))
        self.assertIn("too many letters", text(self.signup(name="A" * 200)))
        self.signup()
        self.assertIn("already registered", text(self.signup()))
        self.assertEqual(self.one("SELECT COUNT(*) FROM users")[0], 1)

    def test_database_refuses_repeated_enrollment(self):
        self.signup()
        with self.assertRaises(sqlite3.IntegrityError):
            db = self.db()
            db.execute("INSERT INTO users (name, enrollment) VALUES ('x', 'E1')")

    def test_wrong_password_and_unknown_user(self):
        self.signup()
        self.assertIn("Wrong enrollment", text(self.login(password="bad")))
        self.assertIn("Wrong enrollment", text(self.login(enrollment="NOPE")))

    def test_pages_need_login(self):
        for url in ["/dashboard", "/report", "/profile", "/teacher/dashboard", "/teacher/student?e=E1",
                    "/teacher/password", "/teacher/export"]:
            self.assertEqual(self.c.get(url).status_code, 302, url)
        for url in ["/addskill", "/updateskill", "/deleteskill", "/projects/add", "/goals/add",
                    "/changepassword", "/teacher/record", "/teacher/attendance", "/teacher/deleterecord",
                    "/teacher/deleteattendance", "/teacher/updateskill", "/teacher/addremark"]:
            self.assertEqual(self.c.post(url, data={}).status_code, 302, url)

    def test_logout_blocks_back_button(self):
        self.student()
        self.c.get("/logout")
        self.assertEqual(self.c.get("/dashboard").status_code, 302)

    def test_session_cookie_settings(self):
        self.assertEqual(A.app.config["SESSION_COOKIE_SAMESITE"], "Lax")
        self.assertTrue(A.app.config["SESSION_COOKIE_HTTPONLY"])
        self.assertTrue(os.path.exists("secret_key.txt") or os.environ.get("STUDENTTRACK_SECRET_KEY"))

    # ===== Skills =====
    def test_skill_add_update_delete(self):
        self.student()
        self.add_skill()
        sid = self.one("SELECT id FROM skills")[0]
        self.c.post("/updateskill", data={"id": sid, "level": "Advanced", "progress": "90",
                                          "category": "Programming", "learning_note": "done"})
        self.assertEqual(self.one("SELECT level, progress FROM skills")[:2], ("Advanced", 90))
        self.c.post("/deleteskill", data={"id": sid})
        self.assertEqual(self.one("SELECT COUNT(*) FROM skills")[0], 0)

    def test_skill_cannot_be_added_twice(self):
        self.student()
        self.add_skill("Python")
        r = self.add_skill("  PYTHON ")
        self.assertIn("#skill-", r.headers["Location"])
        self.assertIn("already in your skills", text(self.c.get("/dashboard")))
        self.assertEqual(self.one("SELECT COUNT(*) FROM skills")[0], 1)

    def test_skill_bad_input_refused(self):
        self.student()
        self.add_skill("X", progress="abc")
        self.add_skill("X", progress="101")
        self.add_skill("X", level="Wizard")
        self.add_skill("A" * 5000)
        self.c.post("/addskill", data={})
        self.assertEqual(self.one("SELECT COUNT(*) FROM skills")[0], 0)

    def test_student_cannot_change_other_students_skill(self):
        self.student("E1", "Ravi")
        self.add_skill()
        sid = self.one("SELECT id FROM skills")[0]
        other = A.app.test_client()
        self.signup("E2", "Sita")
        self.login(other, "E2")
        other.post("/updateskill", data={"id": sid, "level": "Advanced", "progress": "99", "category": "Other"})
        other.post("/deleteskill", data={"id": sid})
        self.assertEqual(self.one("SELECT level, progress FROM skills")[:2], ("Beginner", 20))

    # ===== Projects and goals =====
    def test_projects(self):
        self.student()
        self.c.post("/projects/add", data={"title": "P1", "technologies": "Py", "description": "d",
                                           "project_url": "https://x.com", "status": "Planned"})
        self.c.post("/projects/add", data={"title": "Bad", "project_url": "javascript:alert(1)", "status": "Planned"})
        self.c.post("/projects/add", data={"title": "T" * 500, "status": "Planned"})
        self.c.post("/projects/add", data={"title": "D", "description": "x" * 5000, "status": "Planned"})
        self.assertEqual(self.one("SELECT COUNT(*) FROM projects")[0], 1)
        pid = self.one("SELECT id FROM projects")[0]
        self.c.post("/projects/update", data={"id": pid, "status": "Completed"})
        self.assertEqual(self.one("SELECT status FROM projects")[0], "Completed")
        self.c.post("/projects/update", data={"id": pid, "status": "Nope"})
        self.assertEqual(self.one("SELECT status FROM projects")[0], "Completed")
        self.c.post("/projects/delete", data={"id": pid})
        self.assertEqual(self.one("SELECT COUNT(*) FROM projects")[0], 0)

    def test_goals(self):
        self.student()
        self.c.post("/goals/add", data={"title": "G1", "target_date": "2030-01-31"})
        self.c.post("/goals/add", data={"title": "G2", "target_date": "<script>alert(1)</script>"})
        self.c.post("/goals/add", data={"title": "G" * 400, "target_date": ""})
        self.c.post("/goals/add", data={"title": "", "target_date": ""})
        self.assertEqual(self.one("SELECT COUNT(*) FROM learning_goals")[0], 1)
        gid = self.one("SELECT id FROM learning_goals")[0]
        self.c.post("/goals/toggle", data={"id": gid})
        self.assertEqual(self.one("SELECT completed FROM learning_goals")[0], 1)
        self.c.post("/goals/delete", data={"id": gid})
        self.assertEqual(self.one("SELECT COUNT(*) FROM learning_goals")[0], 0)

    # ===== Profile and password =====
    def test_profile_edit(self):
        self.student()
        r = self.c.post("/profile", data={"name": "Ravi K", "father_name": "Mohan K", "mobile": "9999988888",
                                          "email": "r@k.com"}, follow_redirects=True)
        self.assertIn("Profile updated", text(r))
        self.assertEqual(self.one("SELECT name, father_name, mobile, email FROM users"),
                         ("Ravi K", "Mohan K", "9999988888", "r@k.com"))
        r = self.c.post("/profile", data={"name": "Ravi", "father_name": "M", "mobile": "12", "email": "r@k.com"},
                        follow_redirects=True)
        self.assertIn("10 digits", text(r))

    def test_change_password_rules(self):
        self.student()

        def change(cur, new, conf):
            return text(self.c.post("/changepassword", data={"current": cur, "new": new, "confirm": conf},
                                    follow_redirects=True))
        self.assertIn("Current password is wrong", change("nope", "newpass1", "newpass1"))
        self.assertIn("do not match", change("secret1", "newpass1", "other"))
        self.assertIn("at least 6", change("secret1", "abc", "abc"))
        self.assertIn("different from the old", change("secret1", "secret1", "secret1"))
        self.assertIn("changed successfully", change("secret1", "newpass1", "newpass1"))
        self.c.get("/logout")
        self.assertIn("Wrong enrollment", text(self.login(password="secret1")))
        self.assertEqual(self.login(password="newpass1").status_code, 302)

    # ===== Teacher =====
    def test_teacher_login_and_password_change(self):
        self.assertIn("Wrong teacher", text(self.teacher(password="bad")))
        self.assertEqual(self.teacher().status_code, 302)
        r = self.c.post("/teacher/password", data={"current": "teacher123", "new": "newteach1", "confirm": "newteach1"},
                        follow_redirects=True)
        self.assertIn("changed successfully", text(r))
        self.c.get("/teacher/logout")
        self.assertIn("Wrong teacher", text(self.teacher(password="teacher123")))
        self.assertEqual(self.teacher(password="newteach1").status_code, 302)
        A.make_table()   # restart keeps the new password
        self.c.get("/teacher/logout")
        self.assertEqual(self.teacher(password="newteach1").status_code, 302)

    def test_teacher_marks_add_update_delete(self):
        self.signup()
        self.teacher()
        self.record()
        self.record("MATHS", "10", "10", "10")                  # same subject -> update, no new row
        self.assertEqual(self.one("SELECT COUNT(*), mid_sem FROM academic_records")[:2], (1, 10.0))
        for bad in [("Bad", "31", "1", "1"), ("Bad", "1", "71", "1"), ("Bad", "1", "1", "21"),
                    ("Bad", "-1", "1", "1"), ("Bad", "nan", "1", "1"), ("Bad", "inf", "1", "1"),
                    ("Bad", "", "1", "1"), ("", "1", "1", "1"), ("S" * 100, "1", "1", "1")]:
            self.record(*bad)
        self.c.post("/teacher/record", data={"enrollment": "E1", "subject": "NoFields"})
        self.assertEqual(self.one("SELECT COUNT(*) FROM academic_records")[0], 1)
        rid = self.one("SELECT id FROM academic_records")[0]
        self.c.post("/teacher/deleterecord", data={"id": rid, "enrollment": "E1"})
        self.assertEqual(self.one("SELECT COUNT(*) FROM academic_records")[0], 0)

    def test_teacher_marks_for_unknown_student(self):
        self.teacher()
        self.record(enrollment="NOPE")
        self.assertEqual(self.one("SELECT COUNT(*) FROM academic_records")[0], 0)

    def test_teacher_attendance_add_update_delete(self):
        self.signup()
        self.teacher()
        att = lambda s, t, a: self.c.post("/teacher/attendance", data={"enrollment": "E1", "subject": s,
                                                                      "total_classes": t, "attended_classes": a})
        att("Maths", "40", "28")
        att("maths", "50", "45")
        self.assertEqual(self.one("SELECT COUNT(*), total_classes FROM attendance")[:2], (1, 50))
        att("Bad", "4", "28")
        att("Bad", "4.5", "2")
        att("Bad", "-1", "0")
        att("Bad", "5000", "10")
        att("", "10", "5")
        self.assertEqual(self.one("SELECT COUNT(*) FROM attendance")[0], 1)
        aid = self.one("SELECT id FROM attendance")[0]
        self.c.post("/teacher/deleteattendance", data={"id": aid, "enrollment": "E1"})
        self.assertEqual(self.one("SELECT COUNT(*) FROM attendance")[0], 0)

    def test_teacher_changes_skill_level(self):
        self.student()
        self.add_skill()
        sid = self.one("SELECT id FROM skills")[0]
        t = A.app.test_client()
        self.teacher(t)
        t.post("/teacher/updateskill", data={"id": sid, "enrollment": "E1", "level": "Advanced"})
        self.assertEqual(self.one("SELECT level FROM skills")[0], "Advanced")
        t.post("/teacher/updateskill", data={"id": sid, "enrollment": "E1", "level": "Wizard"})
        t.post("/teacher/updateskill", data={"id": sid, "enrollment": "E2", "level": "Beginner"})
        self.assertEqual(self.one("SELECT level FROM skills")[0], "Advanced")
        self.assertIn("Advanced", text(self.c.get("/dashboard")))

    def test_teacher_remark_reaches_student(self):
        self.student()
        t = A.app.test_client()
        self.teacher(t)
        t.post("/teacher/addremark", data={"enrollment": "E1", "remark": "Well done"})
        t.post("/teacher/addremark", data={"enrollment": "E1", "remark": "R" * 2000})
        t.post("/teacher/addremark", data={"enrollment": "NOPE", "remark": "ghost"})
        self.assertEqual(self.one("SELECT COUNT(*) FROM remarks")[0], 1)
        self.assertIn("Well done", text(self.c.get("/dashboard")))

    def test_teacher_dashboard_numbers_and_search(self):
        self.signup("E1", "Ravi")
        self.signup("E2", "Sita")
        self.teacher()
        self.record("Maths", "5", "10", "2", "E1")             # 17/120 = 14%  -> needs attention
        self.record("Maths", "28", "65", "19", "E2")           # 112/120 = 93% -> excellent
        self.c.post("/teacher/attendance", data={"enrollment": "E1", "subject": "Maths", "total_classes": "40", "attended_classes": "20"})
        self.c.post("/teacher/attendance", data={"enrollment": "E2", "subject": "Maths", "total_classes": "40", "attended_classes": "38"})
        h = text(self.c.get("/teacher/dashboard"))
        self.assertIn("Ravi", h)
        self.assertIn("Sita", h)
        self.assertIn("Low attendance", h)
        db = self.db()
        rows = A.load_all_students(db)
        self.assertEqual([(r[0], r[2], r[4], r[5]) for r in rows], [("Ravi", 14, "Needs attention", 50.0), ("Sita", 93, "Excellent", 95.0)])
        found = text(self.c.get("/teacher/dashboard?q=sita"))
        self.assertIn("<td><b>Sita</b></td>", found)
        self.assertNotIn("<td><b>Ravi</b></td>", found)      # (the "open student" list still shows everyone)

    def test_teacher_student_page_unknown_student(self):
        self.teacher()
        self.assertEqual(self.c.get("/teacher/student?e=NOPE").status_code, 200)
        self.assertEqual(self.c.get("/teacher/student").status_code, 200)
        self.assertEqual(self.c.get("/teacher/student?e=NOPE&edit_mark=abc").status_code, 200)

    def test_export_csv(self):
        self.signup("E1", "=HYPERLINK(\"http://evil\")")
        self.signup("E2", "Sita")
        self.teacher()
        r = self.c.get("/teacher/export")
        self.assertEqual(r.status_code, 200)
        self.assertIn("text/csv", r.headers["Content-Type"])
        self.assertIn("attachment", r.headers["Content-Disposition"])
        body = text(r)
        self.assertIn("Name,Enrollment,Average %", body)
        self.assertIn("Sita,E2", body)
        self.assertIn("'=HYPERLINK", body)                       # formula is made harmless
        self.assertNotIn(",=HYPERLINK", body.replace("\"'=", ""))

    # ===== Recommendations =====
    def test_recommendations(self):
        self.student()
        h = text(self.c.get("/dashboard"))
        self.assertIn("has not added your marks", h)
        self.assertIn("Add your first skill", h)
        t = A.app.test_client()
        self.teacher(t)
        t.post("/teacher/record", data={"enrollment": "E1", "subject": "Maths", "mid_sem": "5", "end_sem": "10", "internal_lab": "2"})
        t.post("/teacher/record", data={"enrollment": "E1", "subject": "Physics", "mid_sem": "28", "end_sem": "65", "internal_lab": "19"})
        t.post("/teacher/attendance", data={"enrollment": "E1", "subject": "Maths", "total_classes": "40", "attended_classes": "28"})
        self.add_skill("Python", "Beginner", "10")
        self.c.post("/goals/add", data={"title": "Old goal", "target_date": "2000-01-01"})
        h = text(self.c.get("/dashboard"))
        self.assertIn("Maths: your result is low", h)
        self.assertIn("Physics: very good result", h)
        self.assertIn("Attend the next 8 classes", h)           # 36 of 48 classes = 75%
        self.assertIn("Python: practise a little every day", h)
        self.assertIn("past its target date", h)
        self.assertIn("Build a small project", h)

    def test_attendance_formula_reaches_75_percent(self):
        for total, attended in [(40, 28), (10, 0), (7, 3), (100, 74)]:
            need = 3 * total - 4 * attended
            self.assertGreaterEqual((attended + need) * 100 / (total + need), 75)

    # ===== Database migration and indexes =====
    def test_old_marks_migrate_only_once(self):
        self.signup()
        db = self.db()
        db.execute("DELETE FROM academic_records")
        db.execute("PRAGMA user_version = 0")
        db.execute("INSERT INTO marks (enrollment, subject, marks) VALUES ('E1', 'Old', 80)")
        db.commit()
        db.close()
        A.make_table()
        self.assertEqual(self.one("SELECT COUNT(*) FROM academic_records WHERE subject='Old'")[0], 1)
        db = self.db()
        db.execute("DELETE FROM academic_records WHERE subject='Old'")
        db.commit()
        db.close()
        A.make_table()                                          # restart
        self.assertEqual(self.one("SELECT COUNT(*) FROM academic_records WHERE subject='Old'")[0], 0)

    def test_indexes_exist(self):
        names = [r[0] for r in self.db().execute("SELECT name FROM sqlite_master WHERE type='index'")]
        for n in ["idx_users_enrollment", "idx_skills_enrollment", "idx_projects_enrollment", "idx_goals_enrollment",
                  "idx_remarks_enrollment", "idx_users_enrollment_unique"]:
            self.assertIn(n, names)

    def test_report_page(self):
        self.student()
        self.assertEqual(self.c.get("/report").status_code, 200)

    def test_student_and_teacher_sessions_are_separate(self):
        self.student()
        self.assertEqual(self.c.get("/teacher/dashboard").status_code, 302)
        t = A.app.test_client()
        self.teacher(t)
        self.assertEqual(t.get("/dashboard").status_code, 302)


if __name__ == "__main__":
    unittest.main(verbosity=2)
