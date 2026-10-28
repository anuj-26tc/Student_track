from flask import Flask, render_template

app = Flask(__name__)

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

app.run(debug=True)