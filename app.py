from flask import Flask, render_template, request, redirect, session
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3

app = Flask(__name__)
app.secret_key = "mysecretkey123"


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
            level TEXT
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
    db.commit()
    db.close()


# This stops the browser from saving old pages (fixes the Back button problem)
@app.after_request
def no_cache(response):
    response.headers["Cache-Control"] = "no-store"
    return response


# ===== MODULE 1: Login and Sign Up =====

@app.route("/")
def home():
    return render_template("index.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    error = ""

    if request.method == "POST":
        enrollment = request.form["enrollment"]
        password = request.form["password"]

        db = sqlite3.connect("students.db")
        user = db.execute(
            "SELECT password FROM users WHERE enrollment = ?",
            (enrollment,)
        ).fetchone()
        db.close()

        # user[0] is the saved (hashed) password
        if user and check_password_hash(user[0], password):
            session["enrollment"] = enrollment
            return redirect("/dashboard")
        else:
            error = "Wrong enrollment no or password"

    return render_template("login.html", error=error)


@app.route("/sign")
def sign():
    return render_template("sign.html", error="")


@app.route("/signup", methods=["POST"])
def signup():
    name = request.form["username"]
    father_name = request.form["Father_name"]
    enrollment = request.form["Enrollment"]
    mobile = request.form["Mobile"]
    email = request.form["Gmail"]
    password = generate_password_hash(request.form["password"])

    db = sqlite3.connect("students.db")

    # Check if this enrollment number is already used
    old = db.execute(
        "SELECT id FROM users WHERE enrollment = ?",
        (enrollment,)
    ).fetchone()

    if old:
        db.close()
        return render_template("sign.html", error="This enrollment no is already registered")

    db.execute(
        "INSERT INTO users (name, father_name, enrollment, mobile, email, password) VALUES (?, ?, ?, ?, ?, ?)",
        (name, father_name, enrollment, mobile, email, password)
    )
    db.commit()
    db.close()

    return redirect("/login")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# ===== MODULE 2: Dashboard =====

@app.route("/dashboard")
def dashboard():
    if "enrollment" not in session:
        return redirect("/login")

    db = sqlite3.connect("students.db")
    user = db.execute(
        "SELECT name FROM users WHERE enrollment = ?",
        (session["enrollment"],)
    ).fetchone()
    skills = db.execute(
        "SELECT skill_name, level FROM skills WHERE enrollment = ?",
        (session["enrollment"],)
    ).fetchall()
    marks = db.execute(
        "SELECT subject, marks FROM marks WHERE enrollment = ?",
        (session["enrollment"],)
    ).fetchall()
    db.close()

    if user is None:
        return redirect("/login")

    # Find the average of all marks
    average = 0
    if len(marks) > 0:
        total = 0
        for m in marks:
            total = total + m[1]
        average = round(total / len(marks))

    return render_template("dashboard.html", name=user[0], skills=skills, marks=marks, average=average)


# ===== MODULE 3: Skills =====

@app.route("/addskill", methods=["POST"])
def addskill():
    if "enrollment" not in session:
        return redirect("/login")

    skill = request.form["skill"].strip()
    level = request.form["level"]

    # If the skill name is empty, do nothing
    if skill == "":
        return redirect("/dashboard")

    db = sqlite3.connect("students.db")
    db.execute(
        "INSERT INTO skills (enrollment, skill_name, level) VALUES (?, ?, ?)",
        (session["enrollment"], skill, level)
    )
    db.commit()
    db.close()

    return redirect("/dashboard")


# ===== MODULE 4: Marks =====

@app.route("/addmark", methods=["POST"])
def addmark():
    if "enrollment" not in session:
        return redirect("/login")

    subject = request.form["subject"].strip()

    # Marks must be a number
    try:
        marks = int(request.form["marks"])
    except ValueError:
        return redirect("/dashboard")

    # Marks must be between 0 and 100, and subject must not be empty
    if marks < 0 or marks > 100 or subject == "":
        return redirect("/dashboard")

    db = sqlite3.connect("students.db")
    db.execute(
        "INSERT INTO marks (enrollment, subject, marks) VALUES (?, ?, ?)",
        (session["enrollment"], subject, marks)
    )
    db.commit()
    db.close()

    return redirect("/dashboard")


make_table()
app.run(debug=True)