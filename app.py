from flask import Flask, render_template, request, redirect, url_for, session, flash
from werkzeug.security import generate_password_hash, check_password_hash
import sqlite3
from pathlib import Path

app = Flask(__name__)
app.secret_key = "change-this-in-production"
DB_PATH = Path(__file__).with_name("student_success.db")


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with get_db() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                email TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS courses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                code TEXT,
                target_grade REAL DEFAULT 85,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS assignments (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                course_id INTEGER NOT NULL,
                title TEXT NOT NULL,
                due_date TEXT,
                score REAL,
                max_score REAL DEFAULT 100,
                weight REAL DEFAULT 1,
                completed INTEGER DEFAULT 0,
                FOREIGN KEY(course_id) REFERENCES courses(id)
            );
            """
        )


def login_required(view):
    from functools import wraps

    @wraps(view)
    def wrapped(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))
        return view(*args, **kwargs)

    return wrapped


def calculate_course_average(assignments):
    graded = [a for a in assignments if a["score"] is not None and a["max_score"]]
    if not graded:
        return None
    total_weight = sum(a["weight"] or 1 for a in graded)
    weighted = sum((a["score"] / a["max_score"] * 100) * (a["weight"] or 1) for a in graded)
    return round(weighted / total_weight, 1) if total_weight else None


@app.route("/")
def index():
    return redirect(url_for("dashboard" if "user_id" in session else "login"))


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        if not name or not email or len(password) < 6:
            flash("Enter a name, email, and password of at least 6 characters.", "error")
            return render_template("register.html")

        try:
            with get_db() as conn:
                cur = conn.execute(
                    "INSERT INTO users (name, email, password_hash) VALUES (?, ?, ?)",
                    (name, email, generate_password_hash(password)),
                )
                session["user_id"] = cur.lastrowid
                session["user_name"] = name
            return redirect(url_for("dashboard"))
        except sqlite3.IntegrityError:
            flash("That email is already registered.", "error")

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]
        with get_db() as conn:
            user = conn.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()

        if user and check_password_hash(user["password_hash"], password):
            session["user_id"] = user["id"]
            session["user_name"] = user["name"]
            return redirect(url_for("dashboard"))

        flash("Invalid email or password.", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


@app.route("/dashboard")
@login_required
def dashboard():
    with get_db() as conn:
        courses = conn.execute(
            "SELECT * FROM courses WHERE user_id = ? ORDER BY name", (session["user_id"],)
        ).fetchall()

        course_cards = []
        all_assignments = []
        for course in courses:
            assignments = conn.execute(
                "SELECT * FROM assignments WHERE course_id = ? ORDER BY due_date", (course["id"],)
            ).fetchall()
            avg = calculate_course_average(assignments)
            course_cards.append({"course": course, "average": avg, "assignments": assignments})
            all_assignments.extend(assignments)

    completed = sum(1 for a in all_assignments if a["completed"])
    completion_rate = round(completed / len(all_assignments) * 100) if all_assignments else 0
    graded_avgs = [c["average"] for c in course_cards if c["average"] is not None]
    overall_avg = round(sum(graded_avgs) / len(graded_avgs), 1) if graded_avgs else None

    chart_labels = [c["course"]["code"] or c["course"]["name"] for c in course_cards]
    chart_values = [c["average"] or 0 for c in course_cards]

    return render_template(
        "dashboard.html",
        course_cards=course_cards,
        overall_avg=overall_avg,
        completion_rate=completion_rate,
        chart_labels=chart_labels,
        chart_values=chart_values,
    )


@app.route("/courses/add", methods=["POST"])
@login_required
def add_course():
    name = request.form["name"].strip()
    code = request.form.get("code", "").strip()
    target = request.form.get("target_grade", 85)
    if name:
        with get_db() as conn:
            conn.execute(
                "INSERT INTO courses (user_id, name, code, target_grade) VALUES (?, ?, ?, ?)",
                (session["user_id"], name, code, float(target or 85)),
            )
    return redirect(url_for("dashboard"))


@app.route("/assignments/add", methods=["POST"])
@login_required
def add_assignment():
    course_id = request.form["course_id"]
    title = request.form["title"].strip()
    due_date = request.form.get("due_date") or None
    score = request.form.get("score")
    max_score = request.form.get("max_score") or 100
    weight = request.form.get("weight") or 1
    completed = 1 if request.form.get("completed") else 0

    with get_db() as conn:
        course = conn.execute(
            "SELECT id FROM courses WHERE id = ? AND user_id = ?", (course_id, session["user_id"])
        ).fetchone()
        if course and title:
            conn.execute(
                """INSERT INTO assignments
                   (course_id, title, due_date, score, max_score, weight, completed)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    course_id,
                    title,
                    due_date,
                    float(score) if score else None,
                    float(max_score),
                    float(weight),
                    completed,
                ),
            )
    return redirect(url_for("dashboard"))


@app.route("/assignments/<int:assignment_id>/toggle", methods=["POST"])
@login_required
def toggle_assignment(assignment_id):
    with get_db() as conn:
        assignment = conn.execute(
            """SELECT a.id, a.completed FROM assignments a
               JOIN courses c ON a.course_id = c.id
               WHERE a.id = ? AND c.user_id = ?""",
            (assignment_id, session["user_id"]),
        ).fetchone()
        if assignment:
            conn.execute(
                "UPDATE assignments SET completed = ? WHERE id = ?",
                (0 if assignment["completed"] else 1, assignment_id),
            )
    return redirect(url_for("dashboard"))


@app.route("/forecast", methods=["POST"])
@login_required
def forecast():
    current = float(request.form["current_grade"])
    target = float(request.form["target_grade"])
    completed_weight = float(request.form["completed_weight"])
    remaining_weight = 100 - completed_weight
    needed = None
    if remaining_weight > 0:
        needed = round((target * 100 - current * completed_weight) / remaining_weight, 1)
    return render_template("forecast.html", needed=needed, current=current, target=target)


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
