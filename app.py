import os
import csv
import io
import datetime
import sqlite3
from flask import Flask, render_template, request, redirect, session, flash, Response
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)


# The secret key protects the login cookie.
# It is made one time with random letters and saved in secret_key.txt (this file is not put on GitHub).
def get_secret_key():
    key = os.environ.get("STUDENTTRACK_SECRET_KEY")
    if key:
        return key
    if not os.path.exists("secret_key.txt"):
        with open("secret_key.txt", "w") as f:
            f.write(os.urandom(24).hex())
    with open("secret_key.txt") as f:
        return f.read().strip()


app.secret_key = get_secret_key()
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"

# First teacher login. It is used only the first time.
# After that the teacher can change the password inside the website.
TEACHER_ID = "teacher"
TEACHER_PASSWORD = "teacher123"


# ===== Database =====

# This makes the database tables (only if they are not made yet)
def make_table():
    db = sqlite3.connect("students.db")
    db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            father_name TEXT,
            enrollment TEXT,
            mobile TEXT,
            email TEXT,
            password TEXT
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS skills (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            enrollment TEXT,
            skill_name TEXT,
            level TEXT,
            category TEXT NOT NULL DEFAULT 'Other'
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS marks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            enrollment TEXT,
            subject TEXT,
            marks INTEGER
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS remarks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            enrollment TEXT,
            remark TEXT
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS academic_records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            enrollment TEXT NOT NULL,
            subject TEXT NOT NULL,
            mid_sem REAL NOT NULL DEFAULT 0,
            end_sem REAL NOT NULL DEFAULT 0,
            internal_lab REAL NOT NULL DEFAULT 0,
            UNIQUE(enrollment, subject)
        )
    """)
    db.execute("""
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            enrollment TEXT NOT NULL,
            subject TEXT NOT NULL,
            total_classes INTEGER NOT NULL DEFAULT 0,
            attended_classes INTEGER NOT NULL DEFAULT 0,
            UNIQUE(enrollment, subject)
        )
    """)
    # Add new skill fields safely to databases created by older versions.
    skill_columns = [row[1] for row in db.execute("PRAGMA table_info(skills)").fetchall()]
    if "progress" not in skill_columns:
        db.execute("ALTER TABLE skills ADD COLUMN progress INTEGER NOT NULL DEFAULT 0")
    if "learning_note" not in skill_columns:
        db.execute("ALTER TABLE skills ADD COLUMN learning_note TEXT DEFAULT ''")
    if "category" not in skill_columns:
        db.execute("ALTER TABLE skills ADD COLUMN category TEXT NOT NULL DEFAULT 'Other'")
    db.execute("UPDATE skills SET level='Intermediate' WHERE level='Medium'")

    # Student-managed project portfolio and learning goals.
    db.execute("""CREATE TABLE IF NOT EXISTS projects (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        enrollment TEXT NOT NULL,
        title TEXT NOT NULL,
        technologies TEXT DEFAULT '',
        description TEXT DEFAULT '',
        project_url TEXT DEFAULT '',
        status TEXT NOT NULL DEFAULT 'In Progress'
    )""")
    db.execute("""CREATE TABLE IF NOT EXISTS learning_goals (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        enrollment TEXT NOT NULL,
        title TEXT NOT NULL,
        target_date TEXT DEFAULT '',
        completed INTEGER NOT NULL DEFAULT 0
    )""")
    # Copy the subjects of the older version (where marks were a percentage) only ONE time.
    # Before this fix it ran at every start, so a deleted subject came back after a restart.
    version = db.execute("PRAGMA user_version").fetchone()[0]
    if version < 1:
        db.execute("""
            INSERT OR IGNORE INTO academic_records (enrollment, subject, mid_sem, end_sem, internal_lab)
            SELECT enrollment, subject, marks * 0.30, marks * 0.70, marks * 0.20
            FROM marks
        """)
        db.execute("PRAGMA user_version = 1")

    db.execute("""
        CREATE TABLE IF NOT EXISTS teacher_account (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_id TEXT,
            password TEXT
        )
    """)

    # Make the first teacher account (only if there is no teacher yet)
    first = db.execute("SELECT id FROM teacher_account").fetchone()
    if first is None:
        db.execute(
            "INSERT INTO teacher_account (teacher_id, password) VALUES (?, ?)",
            (TEACHER_ID, generate_password_hash(TEACHER_PASSWORD))
        )

    db.execute("CREATE INDEX IF NOT EXISTS idx_users_enrollment ON users(enrollment)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_skills_enrollment ON skills(enrollment)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_marks_enrollment ON marks(enrollment)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_remarks_enrollment ON remarks(enrollment)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_projects_enrollment ON projects(enrollment)")
    db.execute("CREATE INDEX IF NOT EXISTS idx_goals_enrollment ON learning_goals(enrollment)")
    # The database itself must also refuse a repeated enrollment number
    try:
        db.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_users_enrollment_unique ON users(enrollment)")
    except sqlite3.IntegrityError:
        pass
    db.commit()
    db.close()


# ===== Small helper functions =====

# Finds the average of marks. Each item in the list is (subject, marks, id)
def find_average(marks):
    if len(marks) == 0:
        return 0
    total = 0
    for m in marks:
        total = total + m[1]
    return round(total / len(marks))


# Gives a status word from the average marks
def find_status(average, count):
    if count == 0:
        return "No data"
    if average < 40:
        return "Needs attention"
    if average < 60:
        return "Average"
    if average < 80:
        return "Good"
    return "Excellent"


# Gives a grade letter from marks
def find_grade(marks):
    if marks >= 90:
        return "A+"
    if marks >= 80:
        return "A"
    if marks >= 70:
        return "B+"
    if marks >= 60:
        return "B"
    if marks >= 50:
        return "C"
    if marks >= 40:
        return "D"
    return "F"


# Checks marks. Gives back a number from 0 to 100, or None if wrong
def check_marks(text):
    try:
        number = int(text)
    except ValueError:
        return None
    if number < 0 or number > 100:
        return None
    return number


# Gets the name, skills, marks and remarks of one student
def load_student(db, enrollment):
    user = db.execute(
        "SELECT name FROM users WHERE enrollment = ?",
        (enrollment,)
    ).fetchone()
    if user is None:
        return None

    skills = db.execute(
        "SELECT skill_name, level, id FROM skills WHERE enrollment = ?",
        (enrollment,)
    ).fetchall()
    marks = db.execute(
        "SELECT subject, marks, id FROM marks WHERE enrollment = ?",
        (enrollment,)
    ).fetchall()
    remarks = db.execute(
        "SELECT remark FROM remarks WHERE enrollment = ? ORDER BY id DESC",
        (enrollment,)
    ).fetchall()
    return user[0], skills, marks, remarks


# Adds the grade letter to every subject: (subject, marks, id, grade)
def add_grades(marks):
    result = []
    for m in marks:
        result.append((m[0], m[1], m[2], find_grade(m[1])))
    return result


# Looks if this subject is already added for this student. Gives the id or None
def find_subject(db, enrollment, subject):
    row = db.execute(
        "SELECT id FROM marks WHERE enrollment = ? AND LOWER(subject) = LOWER(?)",
        (enrollment, subject)
    ).fetchone()
    if row:
        return row[0]
    return None


# Looks if this skill is already added for this student. Gives the id or None
def find_skill(db, enrollment, skill):
    row = db.execute(
        "SELECT id FROM skills WHERE enrollment = ? AND LOWER(skill_name) = LOWER(?)",
        (enrollment, skill)
    ).fetchone()
    if row:
        return row[0]
    return None


# Longest text allowed in each box (so a very long text cannot break the page)
LIMITS = {"subject": 60, "skill": 50, "note": 200, "title": 100, "technologies": 150,
          "description": 500, "url": 300, "goal": 150, "remark": 1000}


def too_long(**texts):
    for key in texts:
        if len(texts[key]) > LIMITS[key]:
            return True
    return False


# Makes the advice list for the student dashboard (this is the small recommendation engine)
def make_tips(academic, percentages, attendance_rows, skills, goals, projects):
    tips = []

    # 1. Advice from marks of every subject
    if len(academic) == 0:
        tips.append("Your teacher has not added your marks yet.")
    for i in range(len(academic)):
        subject = academic[i][1]
        pct = percentages[i]
        if pct < 40:
            tips.append(subject + ": your result is low (" + str(pct) + "%). Revise it every day and ask your teacher for help.")
        elif pct < 60:
            tips.append(subject + ": your result is average (" + str(pct) + "%). Practise more questions.")
        elif pct >= 80:
            tips.append(subject + ": very good result (" + str(pct) + "%). Keep it up!")

    # 2. Advice from attendance (75% is needed)
    for a in attendance_rows:
        total = a[1]
        attended = a[2]
        if total > 0 and attended * 100 / total < 75:
            need = 3 * total - 4 * attended
            tips.append(a[0] + ": attendance is " + str(round(attended * 100 / total, 1)) +
                        "%. Attend the next " + str(need) + " classes in a row to reach 75%.")

    # 3. Advice from skills
    if len(skills) == 0:
        tips.append("Add your first skill to start tracking your growth.")
    for s in skills:
        # s = (id, skill_name, level, progress, learning_note, category)
        if s[2] == "Beginner" and s[3] < 30:
            tips.append(s[1] + ": practise a little every day to move from Beginner to Intermediate.")
        elif s[3] >= 80 and s[2] != "Advanced":
            tips.append(s[1] + ": your progress is " + str(s[3]) + "%. Think about moving to the next level.")

    # 4. Advice from projects and goals
    if len(skills) > 0 and len(projects) == 0:
        tips.append("Build a small project with your skills and add it to your portfolio.")
    if len(goals) == 0:
        tips.append("Set a learning goal with a target date.")
    today = datetime.date.today().isoformat()
    for g in goals:
        # g = (id, title, target_date, completed)
        if not g[3] and g[2] and g[2] < today:
            tips.append("Goal \"" + g[1] + "\" is past its target date. Finish it or choose a new date.")

    return tips[:12]


# Makes a list of all students: (name, enrollment, average, skills, status, attendance, projects)
def load_all_students(db):
    users = db.execute("SELECT name, enrollment FROM users ORDER BY name").fetchall()
    result = []
    for u in users:
        marks = db.execute(
            "SELECT subject, (mid_sem + end_sem + internal_lab) * 100.0 / 120.0, id FROM academic_records WHERE enrollment = ?",
            (u[1],)
        ).fetchall()
        skill_count = db.execute(
            "SELECT COUNT(*) FROM skills WHERE enrollment = ?", (u[1],)
        ).fetchone()[0]
        project_count = db.execute(
            "SELECT COUNT(*) FROM projects WHERE enrollment = ?", (u[1],)
        ).fetchone()[0]
        att = db.execute(
            "SELECT COALESCE(SUM(total_classes), 0), COALESCE(SUM(attended_classes), 0) FROM attendance WHERE enrollment = ?",
            (u[1],)
        ).fetchone()
        attendance = None
        if att[0] > 0:
            attendance = round(att[1] * 100 / att[0], 1)
        average = find_average(marks)
        status = find_status(average, len(marks))
        result.append((u[0], u[1], average, skill_count, status, attendance, project_count))
    return result


# A cell that starts with = + - @ can run as a formula in Excel. This puts a ' before it.
def safe_cell(value):
    text = str(value)
    if text[:1] in ["=", "+", "-", "@"]:
        return "'" + text
    return text


# This stops the browser from saving old pages (fixes the Back button problem)
@app.after_request
def no_cache(response):
    response.headers["Cache-Control"] = "no-store"
    return response


# ===== MODULE 1: Login, Sign Up, Logout =====

# The first page of the website is the login page
@app.route("/")
def home():
    if "enrollment" in session:
        return redirect("/dashboard")
    return render_template("login.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return redirect("/")

    enrollment = request.form["enrollment"].strip()
    password = request.form["password"]

    db = sqlite3.connect("students.db")
    user = db.execute(
        "SELECT password FROM users WHERE enrollment = ?",
        (enrollment,)
    ).fetchone()
    db.close()

    if user and check_password_hash(user[0], password):
        session.clear()
        session["enrollment"] = enrollment
        return redirect("/dashboard")

    flash("Wrong enrollment no or password", "error")
    return render_template("login.html")


@app.route("/sign")
def sign():
    return render_template("sign.html")


@app.route("/signup", methods=["POST"])
def signup():
    name = request.form["username"].strip()
    father_name = request.form["Father_name"].strip()
    enrollment = request.form["Enrollment"].strip()
    mobile = request.form["Mobile"].strip()
    email = request.form["Gmail"].strip()
    password = request.form["password"]

    if name == "" or father_name == "" or enrollment == "":
        flash("Please fill all the boxes", "error")
        return render_template("sign.html")

    if len(name) > 80 or len(father_name) > 80 or len(enrollment) > 30 or len(email) > 120:
        flash("One of the boxes has too many letters", "error")
        return render_template("sign.html")

    if not mobile.isdigit() or len(mobile) != 10:
        flash("Mobile number must have 10 digits", "error")
        return render_template("sign.html")

    if len(password) < 6:
        flash("Password must have at least 6 characters", "error")
        return render_template("sign.html")

    db = sqlite3.connect("students.db")

    old = db.execute(
        "SELECT id FROM users WHERE enrollment = ?",
        (enrollment,)
    ).fetchone()

    if old:
        db.close()
        flash("This enrollment no is already registered", "error")
        return render_template("sign.html")

    try:
        db.execute(
            "INSERT INTO users (name, father_name, enrollment, mobile, email, password) VALUES (?, ?, ?, ?, ?, ?)",
            (name, father_name, enrollment, mobile, email, generate_password_hash(password))
        )
        db.commit()
    except sqlite3.IntegrityError:
        db.close()
        flash("This enrollment no is already registered", "error")
        return render_template("sign.html")
    db.close()

    flash("Account created. Please login.", "success")
    return redirect("/")


@app.route("/logout")
def logout():
    session.clear()
    flash("You are logged out", "success")
    return redirect("/")


# ===== MODULE 2: Student Dashboard =====

@app.route("/dashboard")
def dashboard():
    if "enrollment" not in session:
        return redirect("/")
    db = sqlite3.connect("students.db")
    data = load_student(db, session["enrollment"])
    academic = db.execute(
        "SELECT id, subject, mid_sem, end_sem, internal_lab FROM academic_records WHERE enrollment = ? ORDER BY subject",
        (session["enrollment"],)
    ).fetchall()
    attendance_rows = db.execute(
        "SELECT subject, total_classes, attended_classes FROM attendance WHERE enrollment = ? ORDER BY subject",
        (session["enrollment"],)
    ).fetchall()
    skill_rows = db.execute(
        "SELECT id, skill_name, level, progress, learning_note, category FROM skills WHERE enrollment = ? ORDER BY id DESC",
        (session["enrollment"],)
    ).fetchall()
    projects = db.execute(
        "SELECT id, title, technologies, description, project_url, status FROM projects WHERE enrollment=? ORDER BY id DESC",
        (session["enrollment"],)
    ).fetchall()
    goals = db.execute(
        "SELECT id, title, target_date, completed FROM learning_goals WHERE enrollment=? ORDER BY completed, id DESC",
        (session["enrollment"],)
    ).fetchall()
    db.close()
    if data is None:
        session.clear()
        return redirect("/")
    name, old_skills, old_marks, remarks = data
    totals = [r[2] + r[3] + r[4] for r in academic]
    percentages = [round((r[2] + r[3] + r[4]) / 120 * 100, 1) for r in academic]
    average = round(sum(percentages) / len(percentages)) if percentages else 0
    att_total = sum(r[1] for r in attendance_rows)
    att_attended = sum(r[2] for r in attendance_rows)
    attendance_percent = round(att_attended / att_total * 100, 1) if att_total else 0
    status = find_status(average, len(academic))
    tips = make_tips(academic, percentages, attendance_rows, skill_rows, goals, projects)
    return render_template("dashboard.html", name=name, academic=academic,
        attendance_rows=attendance_rows, skills=skill_rows, remarks=remarks,
        average=average, attendance_percent=attendance_percent,
        total_skills=len(skill_rows), status=status, totals=totals,
        percentages=percentages, tips=tips, projects=projects, goals=goals,
        total_projects=len(projects), completed_goals=sum(1 for g in goals if g[3]))


# ===== MODULE 3: Student-managed Skills =====

@app.route("/addskill", methods=["POST"])
def addskill():
    if "enrollment" not in session:
        return redirect("/")
    skill = request.form.get("skill", "").strip()
    level = request.form.get("level", "")
    category = request.form.get("category", "Other")
    note = request.form.get("learning_note", "").strip()
    allowed_categories = ["Programming", "Web Development", "Database", "Communication", "Problem Solving", "Design", "Other"]
    try:
        progress = int(request.form.get("progress", "0"))
    except ValueError:
        progress = -1
    if not skill or level not in ["Beginner", "Intermediate", "Advanced"] or category not in allowed_categories or not 0 <= progress <= 100:
        flash("Enter a skill, valid category/level and progress from 0 to 100.", "error")
        return redirect("/dashboard#skills")
    if too_long(skill=skill, note=note):
        flash("Skill name can have up to 50 letters and the note up to 200 letters.", "error")
        return redirect("/dashboard#skills")
    db = sqlite3.connect("students.db")
    old_id = find_skill(db, session["enrollment"], skill)
    if old_id:
        db.close()
        flash(skill + " is already in your skills. Use Update on that skill.", "warning")
        return redirect("/dashboard#skill-" + str(old_id))
    db.execute("INSERT INTO skills (enrollment, skill_name, level, progress, learning_note, category) VALUES (?, ?, ?, ?, ?, ?)",
               (session["enrollment"], skill, level, progress, note, category))
    db.commit()
    db.close()
    flash("Skill added.", "success")
    return redirect("/dashboard#skills")


@app.route("/updateskill", methods=["POST"])
def updateskill():
    if "enrollment" not in session:
        return redirect("/")
    skill_id = request.form.get("id", "")
    level = request.form.get("level", "")
    try:
        progress = int(request.form.get("progress", "0"))
    except ValueError:
        progress = -1
    note = request.form.get("learning_note", "").strip()
    category = request.form.get("category", "Other")
    allowed_categories = ["Programming", "Web Development", "Database", "Communication", "Problem Solving", "Design", "Other"]
    if level not in ["Beginner", "Intermediate", "Advanced"] or category not in allowed_categories or not 0 <= progress <= 100:
        flash("Choose a valid level and progress from 0 to 100.", "error")
        return redirect("/dashboard#skills")
    if too_long(note=note):
        flash("The note can have up to 200 letters.", "error")
        return redirect("/dashboard#skills")
    db = sqlite3.connect("students.db")
    db.execute("UPDATE skills SET level=?, progress=?, learning_note=?, category=? WHERE id=? AND enrollment=?",
               (level, progress, note, category, skill_id, session["enrollment"]))
    db.commit()
    db.close()
    flash("Skill updated.", "success")
    return redirect("/dashboard#skill-" + skill_id)


@app.route("/deleteskill", methods=["POST"])
def deleteskill():
    if "enrollment" not in session:
        return redirect("/")
    db = sqlite3.connect("students.db")
    db.execute("DELETE FROM skills WHERE id=? AND enrollment=?",
               (request.form.get("id"), session["enrollment"]))
    db.commit()
    db.close()
    flash("Skill deleted.", "success")
    return redirect("/dashboard#skills")


# ===== MODULE 4: Marks =====

# Official academic records are intentionally teacher-managed only.

# ===== MODULE 5: Student Profile =====

@app.route("/profile", methods=["GET", "POST"])
def profile():
    if "enrollment" not in session:
        return redirect("/")

    db = sqlite3.connect("students.db")

    if request.method == "POST":
        name = request.form["name"].strip()
        father_name = request.form["father_name"].strip()
        mobile = request.form["mobile"].strip()
        email = request.form["email"].strip()

        if name == "":
            flash("Name cannot be empty", "error")
        elif father_name == "":
            flash("Father's name cannot be empty", "error")
        elif not mobile.isdigit() or len(mobile) != 10:
            flash("Mobile number must have 10 digits", "error")
        elif email == "":
            flash("Email cannot be empty", "error")
        else:
            db.execute(
                "UPDATE users SET name = ?, father_name = ?, mobile = ?, email = ? WHERE enrollment = ?",
                (name, father_name, mobile, email, session["enrollment"])
            )
            db.commit()
            flash("Profile updated", "success")

        db.close()
        return redirect("/profile")

    user = db.execute(
        "SELECT name, father_name, enrollment, mobile, email FROM users WHERE enrollment = ?",
        (session["enrollment"],)
    ).fetchone()
    db.close()

    if user is None:
        session.clear()
        return redirect("/")

    return render_template("profile.html", user=user)


@app.route("/changepassword", methods=["POST"])
def changepassword():
    if "enrollment" not in session:
        return redirect("/")

    current = request.form["current"]
    new = request.form["new"]
    confirm = request.form["confirm"]

    db = sqlite3.connect("students.db")
    user = db.execute(
        "SELECT password FROM users WHERE enrollment = ?",
        (session["enrollment"],)
    ).fetchone()

    if user is None:
        db.close()
        return redirect("/")

    if not check_password_hash(user[0], current):
        flash("Current password is wrong", "error")
    elif len(new) < 6:
        flash("New password must have at least 6 characters", "error")
    elif new != confirm:
        flash("New password and confirm password do not match", "error")
    elif new == current:
        flash("New password must be different from the old password", "error")
    else:
        db.execute(
            "UPDATE users SET password = ? WHERE enrollment = ?",
            (generate_password_hash(new), session["enrollment"])
        )
        db.commit()
        flash("Password changed successfully", "success")

    db.close()
    return redirect("/profile")


# ===== MODULE 5B: Student projects, goals and growth report =====

@app.route("/projects/add", methods=["POST"])
def add_project():
    if "enrollment" not in session:
        return redirect("/")
    title = request.form.get("title", "").strip()
    technologies = request.form.get("technologies", "").strip()
    description = request.form.get("description", "").strip()
    project_url = request.form.get("project_url", "").strip()
    status = request.form.get("status", "In Progress")
    if not title or status not in ["Planned", "In Progress", "Completed"]:
        flash("Enter a project title and valid status.", "error")
    elif too_long(title=title, technologies=technologies, description=description, url=project_url):
        flash("Project title can have up to 100 letters, technologies 150, description 500 and link 300.", "error")
    elif project_url and not (project_url.startswith("https://") or project_url.startswith("http://")):
        flash("Project link must start with http:// or https://.", "error")
    else:
        db = sqlite3.connect("students.db")
        db.execute("INSERT INTO projects (enrollment, title, technologies, description, project_url, status) VALUES (?, ?, ?, ?, ?, ?)",
                   (session["enrollment"], title, technologies, description, project_url, status))
        db.commit()
        db.close()
        flash("Project added to your portfolio.", "success")
    return redirect("/dashboard#projects")


@app.route("/projects/update", methods=["POST"])
def update_project():
    if "enrollment" not in session:
        return redirect("/")
    project_id = request.form.get("id", "")
    status = request.form.get("status", "")
    if status not in ["Planned", "In Progress", "Completed"]:
        flash("Choose a valid project status.", "error")
    else:
        db = sqlite3.connect("students.db")
        db.execute("UPDATE projects SET status=? WHERE id=? AND enrollment=?", (status, project_id, session["enrollment"]))
        db.commit()
        db.close()
        flash("Project status updated.", "success")
    return redirect("/dashboard#projects")


@app.route("/projects/delete", methods=["POST"])
def delete_project():
    if "enrollment" not in session:
        return redirect("/")
    db = sqlite3.connect("students.db")
    db.execute("DELETE FROM projects WHERE id=? AND enrollment=?", (request.form.get("id"), session["enrollment"]))
    db.commit()
    db.close()
    flash("Project removed.", "success")
    return redirect("/dashboard#projects")


@app.route("/goals/add", methods=["POST"])
def add_goal():
    if "enrollment" not in session:
        return redirect("/")
    title = request.form.get("title", "").strip()
    target_date = request.form.get("target_date", "").strip()
    date_ok = True
    if target_date:
        try:
            datetime.date.fromisoformat(target_date)
        except ValueError:
            date_ok = False
    if not title:
        flash("Enter a learning goal.", "error")
    elif too_long(goal=title):
        flash("A goal can have up to 150 letters.", "error")
    elif not date_ok:
        flash("Choose a valid target date.", "error")
    else:
        db = sqlite3.connect("students.db")
        db.execute("INSERT INTO learning_goals (enrollment, title, target_date) VALUES (?, ?, ?)",
                   (session["enrollment"], title, target_date))
        db.commit()
        db.close()
        flash("Learning goal added.", "success")
    return redirect("/dashboard#goals")


@app.route("/goals/toggle", methods=["POST"])
def toggle_goal():
    if "enrollment" not in session:
        return redirect("/")
    db = sqlite3.connect("students.db")
    db.execute("UPDATE learning_goals SET completed=CASE completed WHEN 0 THEN 1 ELSE 0 END WHERE id=? AND enrollment=?",
               (request.form.get("id"), session["enrollment"]))
    db.commit()
    db.close()
    return redirect("/dashboard#goals")


@app.route("/goals/delete", methods=["POST"])
def delete_goal():
    if "enrollment" not in session:
        return redirect("/")
    db = sqlite3.connect("students.db")
    db.execute("DELETE FROM learning_goals WHERE id=? AND enrollment=?", (request.form.get("id"), session["enrollment"]))
    db.commit()
    db.close()
    return redirect("/dashboard#goals")


@app.route("/report")
def growth_report():
    if "enrollment" not in session:
        return redirect("/")
    db = sqlite3.connect("students.db")
    user = db.execute("SELECT name, enrollment FROM users WHERE enrollment=?", (session["enrollment"],)).fetchone()
    academic = db.execute("SELECT subject, mid_sem, end_sem, internal_lab FROM academic_records WHERE enrollment=? ORDER BY subject", (session["enrollment"],)).fetchall()
    attendance_rows = db.execute("SELECT subject, total_classes, attended_classes FROM attendance WHERE enrollment=? ORDER BY subject", (session["enrollment"],)).fetchall()
    skills = db.execute("SELECT skill_name, category, level, progress FROM skills WHERE enrollment=? ORDER BY skill_name", (session["enrollment"],)).fetchall()
    projects = db.execute("SELECT title, technologies, status FROM projects WHERE enrollment=? ORDER BY title", (session["enrollment"],)).fetchall()
    db.close()
    if not user:
        return redirect("/")
    subject_percentages = [((r[1]+r[2]+r[3])*100/120) for r in academic]
    academic_average = round(sum(subject_percentages)/len(subject_percentages), 1) if subject_percentages else 0
    total_held = sum(r[1] for r in attendance_rows)
    total_attended = sum(r[2] for r in attendance_rows)
    attendance_percent = round(total_attended*100/total_held, 1) if total_held else 0
    return render_template("report.html", user=user, academic=academic, attendance_rows=attendance_rows,
        skills=skills, projects=projects, academic_average=academic_average, attendance_percent=attendance_percent)


# ===== MODULE 6: Teacher =====

@app.route("/teacher", methods=["GET", "POST"])
def teacher_login():
    if request.method == "POST":
        teacher_id = request.form["teacher_id"].strip()
        password = request.form["password"]

        db = sqlite3.connect("students.db")
        teacher = db.execute(
            "SELECT password FROM teacher_account WHERE teacher_id = ?",
            (teacher_id,)
        ).fetchone()
        db.close()

        if teacher and check_password_hash(teacher[0], password):
            session.clear()
            session["teacher"] = teacher_id
            return redirect("/teacher/dashboard")

        flash("Wrong teacher id or password", "error")

    return render_template("teacher_login.html")


@app.route("/teacher/dashboard")
def teacher_dashboard():
    if "teacher" not in session:
        return redirect("/teacher")

    q = request.args.get("q", "").strip()
    search = q.lower()

    db = sqlite3.connect("students.db")
    all_students = load_all_students(db)
    db.close()

    # Numbers for the four cards
    total_students = len(all_students)
    needs_attention = 0
    low_attendance = 0
    class_total = 0
    class_count = 0
    for s in all_students:
        if s[4] == "Needs attention":
            needs_attention = needs_attention + 1
        if s[4] != "No data":
            class_total = class_total + s[2]
            class_count = class_count + 1
        if s[5] is not None and s[5] < 75:
            low_attendance = low_attendance + 1

    class_average = 0
    if class_count > 0:
        class_average = round(class_total / class_count)

    # Keep only the students that match the search
    students = []
    for s in all_students:
        if search == "" or search in s[0].lower() or search in s[1].lower():
            students.append(s)

    return render_template("teacher_dashboard.html", students=students, q=q,
                           total_students=total_students, class_average=class_average,
                           needs_attention=needs_attention, low_attendance=low_attendance,
                           all_students=all_students)


# Teacher downloads the class report as a CSV file (opens in Excel)
@app.route("/teacher/export")
def teacher_export():
    if "teacher" not in session:
        return redirect("/teacher")

    db = sqlite3.connect("students.db")
    all_students = load_all_students(db)
    db.close()

    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["Name", "Enrollment", "Average %", "Attendance %", "Skills", "Projects", "Status"])
    for s in all_students:
        attendance = "" if s[5] is None else s[5]
        writer.writerow([safe_cell(s[0]), safe_cell(s[1]), s[2], attendance, s[3], s[6], s[4]])

    # "\ufeff" lets Excel read the file as UTF-8
    return Response("\ufeff" + out.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=class_report.csv"})


@app.route("/teacher/student")
def teacher_student():
    if "teacher" not in session:
        return redirect("/teacher")
    enrollment = request.args.get("e", "").strip()
    db = sqlite3.connect("students.db")
    user = db.execute("SELECT name, father_name, mobile, email FROM users WHERE enrollment=?", (enrollment,)).fetchone()
    students = db.execute("SELECT enrollment, name FROM users ORDER BY name").fetchall()
    academic = db.execute("SELECT id, subject, mid_sem, end_sem, internal_lab FROM academic_records WHERE enrollment=? ORDER BY subject", (enrollment,)).fetchall()
    attendance_rows = db.execute("SELECT id, subject, total_classes, attended_classes FROM attendance WHERE enrollment=? ORDER BY subject", (enrollment,)).fetchall()
    skills = db.execute("SELECT skill_name, level, id, progress, learning_note, category FROM skills WHERE enrollment=? ORDER BY id DESC", (enrollment,)).fetchall()
    editing_mark = None
    editing_attendance = None
    mark_id = request.args.get("edit_mark", type=int)
    attendance_id = request.args.get("edit_attendance", type=int)
    if mark_id:
        editing_mark = db.execute("SELECT id, subject, mid_sem, end_sem, internal_lab FROM academic_records WHERE id=? AND enrollment=?", (mark_id, enrollment)).fetchone()
    if attendance_id:
        editing_attendance = db.execute("SELECT id, subject, total_classes, attended_classes FROM attendance WHERE id=? AND enrollment=?", (attendance_id, enrollment)).fetchone()
    projects = db.execute("SELECT title, technologies, description, project_url, status FROM projects WHERE enrollment=? ORDER BY id DESC", (enrollment,)).fetchall()
    remarks = db.execute("SELECT remark FROM remarks WHERE enrollment=? ORDER BY id DESC", (enrollment,)).fetchall()
    db.close()
    if user is None:
        return render_template("student_detail.html", enrollment="", user=None, students=students,
            academic=[], attendance_rows=[], skills=[], projects=[], remarks=[])
    return render_template("student_detail.html", enrollment=enrollment, user=user, students=students,
        academic=academic, attendance_rows=attendance_rows, skills=skills, projects=projects, remarks=remarks,
        editing_mark=editing_mark, editing_attendance=editing_attendance)


@app.route("/teacher/record", methods=["POST"])
def teacher_save_record():
    if "teacher" not in session:
        return redirect("/teacher")
    enrollment = request.form.get("enrollment", "").strip()
    subject = request.form.get("subject", "").strip()
    try:
        mid = float(request.form.get("mid_sem", ""))
        end = float(request.form.get("end_sem", ""))
        internal = float(request.form.get("internal_lab", ""))
    except ValueError:
        flash("Marks must be numeric.", "error")
        return redirect("/teacher/student?e=" + enrollment)
    if not subject or not (0 <= mid <= 30 and 0 <= end <= 70 and 0 <= internal <= 20):
        flash("Check subject and marks: Mid-Sem 0-30, End-Sem 0-70, Internal/Lab 0-20.", "error")
    elif too_long(subject=subject):
        flash("Subject name can have up to 60 letters.", "error")
    else:
        db = sqlite3.connect("students.db")
        student_exists = db.execute("SELECT 1 FROM users WHERE enrollment=?", (enrollment,)).fetchone()
        if not student_exists:
            db.close()
            flash("Student not found.", "error")
            return redirect("/teacher/dashboard")
        existing = db.execute("SELECT id FROM academic_records WHERE enrollment=? AND LOWER(subject)=LOWER(?)", (enrollment, subject)).fetchone()
        if existing:
            db.execute("UPDATE academic_records SET mid_sem=?, end_sem=?, internal_lab=? WHERE id=?",
                       (mid, end, internal, existing[0]))
            message = "Academic marks updated."
        else:
            db.execute("INSERT INTO academic_records (enrollment, subject, mid_sem, end_sem, internal_lab) VALUES (?, ?, ?, ?, ?)",
                       (enrollment, subject, mid, end, internal))
            message = "Academic marks saved."
        db.commit()
        db.close()
        flash(message, "success")
    return redirect("/teacher/student?e=" + enrollment + "#academics")


@app.route("/teacher/attendance", methods=["POST"])
def teacher_save_attendance():
    if "teacher" not in session:
        return redirect("/teacher")
    enrollment = request.form.get("enrollment", "").strip()
    subject = request.form.get("subject", "").strip()
    try:
        total = int(request.form.get("total_classes", ""))
        attended = int(request.form.get("attended_classes", ""))
    except ValueError:
        total, attended = -1, -1
    if not subject or total < 0 or attended < 0 or attended > total:
        flash("Enter valid attendance. Attended classes cannot exceed total classes.", "error")
    elif too_long(subject=subject) or total > 1000:
        flash("Subject name can have up to 60 letters and total classes up to 1000.", "error")
    else:
        db = sqlite3.connect("students.db")
        student_exists = db.execute("SELECT 1 FROM users WHERE enrollment=?", (enrollment,)).fetchone()
        if not student_exists:
            db.close()
            flash("Student not found.", "error")
            return redirect("/teacher/dashboard")
        existing = db.execute("SELECT id FROM attendance WHERE enrollment=? AND LOWER(subject)=LOWER(?)", (enrollment, subject)).fetchone()
        if existing:
            db.execute("UPDATE attendance SET total_classes=?, attended_classes=? WHERE id=?",
                       (total, attended, existing[0]))
            message = "Attendance updated."
        else:
            db.execute("INSERT INTO attendance (enrollment, subject, total_classes, attended_classes) VALUES (?, ?, ?, ?)",
                       (enrollment, subject, total, attended))
            message = "Attendance saved."
        db.commit()
        db.close()
        flash(message, "success")
    return redirect("/teacher/student?e=" + enrollment + "#attendance")


# Teacher deletes a wrong marks entry
@app.route("/teacher/deleterecord", methods=["POST"])
def teacher_delete_record():
    if "teacher" not in session:
        return redirect("/teacher")

    enrollment = request.form.get("enrollment", "").strip()
    db = sqlite3.connect("students.db")
    db.execute("DELETE FROM academic_records WHERE id = ? AND enrollment = ?",
               (request.form.get("id"), enrollment))
    db.commit()
    db.close()
    flash("Marks entry deleted.", "success")
    return redirect("/teacher/student?e=" + enrollment + "#academics")


# Teacher deletes a wrong attendance entry
@app.route("/teacher/deleteattendance", methods=["POST"])
def teacher_delete_attendance():
    if "teacher" not in session:
        return redirect("/teacher")

    enrollment = request.form.get("enrollment", "").strip()
    db = sqlite3.connect("students.db")
    db.execute("DELETE FROM attendance WHERE id = ? AND enrollment = ?",
               (request.form.get("id"), enrollment))
    db.commit()
    db.close()
    flash("Attendance entry deleted.", "success")
    return redirect("/teacher/student?e=" + enrollment + "#attendance")


# Teacher changes the level of a student's skill
@app.route("/teacher/updateskill", methods=["POST"])
def teacher_update_skill():
    if "teacher" not in session:
        return redirect("/teacher")

    enrollment = request.form.get("enrollment", "").strip()
    skill_id = request.form.get("id", "")
    level = request.form.get("level", "")

    if level not in ["Beginner", "Intermediate", "Advanced"]:
        flash("Choose Beginner, Intermediate or Advanced.", "error")
    else:
        db = sqlite3.connect("students.db")
        db.execute("UPDATE skills SET level = ? WHERE id = ? AND enrollment = ?",
                   (level, skill_id, enrollment))
        db.commit()
        db.close()
        flash("Skill level updated.", "success")
    return redirect("/teacher/student?e=" + enrollment + "#skills")


# Teacher changes his own password
@app.route("/teacher/password", methods=["GET", "POST"])
def teacher_password():
    if "teacher" not in session:
        return redirect("/teacher")

    if request.method == "POST":
        current = request.form["current"]
        new = request.form["new"]
        confirm = request.form["confirm"]

        db = sqlite3.connect("students.db")
        teacher = db.execute(
            "SELECT password FROM teacher_account WHERE teacher_id = ?",
            (session["teacher"],)
        ).fetchone()

        if teacher is None:
            db.close()
            session.clear()
            return redirect("/teacher")

        if not check_password_hash(teacher[0], current):
            flash("Current password is wrong", "error")
        elif len(new) < 6:
            flash("New password must have at least 6 characters", "error")
        elif new != confirm:
            flash("New password and confirm password do not match", "error")
        elif new == current:
            flash("New password must be different from the old password", "error")
        else:
            db.execute(
                "UPDATE teacher_account SET password = ? WHERE teacher_id = ?",
                (generate_password_hash(new), session["teacher"])
            )
            db.commit()
            flash("Password changed successfully", "success")

        db.close()
        return redirect("/teacher/password")

    return render_template("teacher_password.html")


@app.route("/teacher/addremark", methods=["POST"])
def teacher_addremark():
    if "teacher" not in session:
        return redirect("/teacher")

    enrollment = request.form.get("enrollment", "").strip()
    remark = request.form.get("remark", "").strip()

    if len(remark) > LIMITS["remark"]:
        flash("A remark can have up to 1000 letters.", "error")
    elif remark:
        db = sqlite3.connect("students.db")
        student_exists = db.execute("SELECT 1 FROM users WHERE enrollment=?", (enrollment,)).fetchone()
        if student_exists:
            db.execute("INSERT INTO remarks (enrollment, remark) VALUES (?, ?)", (enrollment, remark[:1000]))
            db.commit()
            flash("Feedback added", "success")
        else:
            flash("Student not found.", "error")
        db.close()

    return redirect("/teacher/student?e=" + enrollment + "#feedback")


@app.route("/teacher/logout")
def teacher_logout():
    session.clear()
    flash("You are logged out", "success")
    return redirect("/teacher")


make_table()

if __name__ == "__main__":
    app.run(debug=False)
