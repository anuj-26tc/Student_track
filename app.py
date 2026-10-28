from flask import Flask, render_template, request, redirect, session
import sqlite3

app = Flask(__name__)
app.secret_key = "mysecretkey123"



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
    db.commit()
    db.close()


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
            "SELECT * FROM users WHERE enrollment = ? AND password = ?",
            (enrollment, password)
        ).fetchone()
        db.close()

        if user:
            session["enrollment"] = enrollment
            return redirect("/dashboard")
        else:
            error = "Wrong enrollment no or password"

    return render_template("login.html", error=error)


@app.route("/sign")
def sign():
    return render_template("sign.html")



@app.route("/signup", methods=["POST"])
def signup():
    name = request.form["username"]
    father_name = request.form["Father_name"]
    enrollment = request.form["Enrollment"]
    mobile = request.form["Mobile"]
    email = request.form["Gmail"]
    password = request.form["password"]

    db = sqlite3.connect("students.db")
    db.execute(
        "INSERT INTO users (name, father_name, enrollment, mobile, email, password) VALUES (?, ?, ?, ?, ?, ?)",
        (name, father_name, enrollment, mobile, email, password)
    )
    db.commit()
    db.close()

    return redirect("/login")



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
    db.close()

    if user is None:
        return redirect("/login")

    return render_template("dashboard.html", name=user[0], skills=skills)



@app.route("/addskill", methods=["POST"])
def addskill():
    if "enrollment" not in session:
        return redirect("/login")

    skill = request.form["skill"]
    level = request.form["level"]

    db = sqlite3.connect("students.db")
    db.execute(
        "INSERT INTO skills (enrollment, skill_name, level) VALUES (?, ?, ?)",
        (session["enrollment"], skill, level)
    )
    db.commit()
    db.close()

    return redirect("/dashboard")



@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")



@app.route("/users")
def users():
    db = sqlite3.connect("students.db")
    rows = db.execute("SELECT * FROM users").fetchall()
    db.close()
    return str(rows)


make_table()
app.run(debug=True)