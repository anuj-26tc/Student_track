from flask import Flask, render_template, request, redirect
import sqlite3

app = Flask(__name__)

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
    db.commit()
    db.close()


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/login")
def login():
    return render_template("login.html")


@app.route("/sign")
def sign():
    return render_template("sign.html")


@app.route("/dashboard")
def dashboard():
    return render_template("dashboard.html")


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


@app.route("/users")
def users():
    db = sqlite3.connect("students.db")
    rows = db.execute("SELECT * FROM users").fetchall()
    db.close()
    return str(rows)


make_table()
app.run(debug=True)