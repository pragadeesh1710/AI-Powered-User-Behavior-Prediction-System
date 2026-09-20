from flask import Flask, render_template, session, request, redirect, url_for, flash, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from recommendation import recommend_courses, get_user_interest_summary, get_related_courses, get_popular_courses
from database import get_connection, create_tables
from seed_data import seed
import os

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "change-this-secret-key")

create_tables()
seed()


@app.context_processor
def utility_processor():
    def category_icon(category):
        icons = {
            "Programming": "🐍",
            "AI & ML": "🤖",
            "Data Science": "📊",
            "Design": "🎨",
            "Web Development": "🌐",
            "Cyber Security": "🔐",
            "Cloud Computing": "☁️",
        }
        return icons.get(category, "📚")
    return {"category_icon": category_icon}


def logged_in():
    return bool(session.get("user_id"))


@app.route("/")
def home():
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("SELECT DISTINCT category FROM courses ORDER BY category")
    categories = [r["category"] for r in cursor.fetchall()]
    cursor.execute("SELECT * FROM courses ORDER BY course_id DESC LIMIT 6")
    featured = cursor.fetchall()
    connection.close()
    recommendations = recommend_courses(session["user_id"], 6) if logged_in() else get_popular_courses(6)
    return render_template("index.html", categories=categories, featured=featured, recommendations=recommendations)


@app.route("/courses")
def courses():
    q = request.args.get("q", "").strip()
    category = request.args.get("category", "").strip()

    connection = get_connection()
    cursor = connection.cursor()

    if q and logged_in():
        cursor.execute(
            "INSERT INTO search_history (user_id, query) VALUES (?, ?)",
            (session["user_id"], q)
        )
        connection.commit()

    query = "SELECT * FROM courses WHERE 1=1"
    params = []

    if q:
        query += " AND (name LIKE ? OR description LIKE ? OR category LIKE ?)"
        term = f"%{q}%"
        params.extend([term, term, term])

    if category and category != "All":
        query += " AND category = ?"
        params.append(category)

    query += " ORDER BY name"

    cursor.execute(query, params)
    all_courses = cursor.fetchall()

    cursor.execute("SELECT DISTINCT category FROM courses ORDER BY category")
    categories = [r["category"] for r in cursor.fetchall()]

    connection.close()

    return render_template(
        "products.html",
        courses=all_courses,
        categories=categories,
        q=q,
        selected_category=category or "All"
    )


@app.route("/course/<int:course_id>")
def course_details(course_id):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        "SELECT * FROM courses WHERE course_id = ?",
        (course_id,)
    )
    course = cursor.fetchone()

    if not course:
        connection.close()
        flash("Course not found.", "error")
        return redirect(url_for("courses"))

    if logged_in():
        cursor.execute(
            "INSERT INTO user_activity (user_id, course_id, activity_type) VALUES (?, ?, 'view')",
            (session["user_id"], course_id)
        )
        connection.commit()

    cursor.execute(
        "SELECT * FROM favorites WHERE user_id = ? AND course_id = ?",
        (session["user_id"], course_id)
    ) if logged_in() else None

    favorite = bool(cursor.fetchone()) if logged_in() else False

    user_rating = None

    if logged_in():
        cursor.execute(
            "SELECT rating FROM ratings WHERE user_id = ? AND course_id = ?",
            (session["user_id"], course_id)
        )

        rating_row = cursor.fetchone()
        user_rating = rating_row["rating"] if rating_row else None

    connection.close()

    related = get_related_courses(course_id, 6)

    return render_template(
        "course_details.html",
        course=course,
        related=related,
        favorite=favorite,
        user_rating=user_rating
    )


@app.route("/api/course/<int:course_id>/time", methods=["POST"])
def record_time(course_id):
    if not logged_in():
        return jsonify({"ok": False, "message": "Login required"}), 401

    data = request.get_json(silent=True) or {}

    seconds = int(data.get("seconds", 0) or 0)
    seconds = max(0, min(seconds, 120))

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO course_time (user_id, course_id, seconds)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id, course_id)
        DO UPDATE SET seconds = seconds + excluded.seconds,
                      updated_at = CURRENT_TIMESTAMP
    """, (session["user_id"], course_id, seconds))

    connection.commit()
    connection.close()

    return jsonify({"ok": True})


@app.route("/course/<int:course_id>/favorite", methods=["POST"])
def favorite(course_id):
    if not logged_in():
        flash("Please log in to save favorites.", "error")
        return redirect(url_for("login"))

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        "SELECT 1 FROM favorites WHERE user_id = ? AND course_id = ?",
        (session["user_id"], course_id)
    )

    exists = cursor.fetchone()

    if exists:
        cursor.execute(
            "DELETE FROM favorites WHERE user_id = ? AND course_id = ?",
            (session["user_id"], course_id)
        )

        cursor.execute(
            "INSERT INTO user_activity (user_id, course_id, activity_type) VALUES (?, ?, 'unfavorite')",
            (session["user_id"], course_id)
        )

        message = "Removed from favorites."

    else:
        cursor.execute(
            "INSERT INTO favorites (user_id, course_id) VALUES (?, ?)",
            (session["user_id"], course_id)
        )

        cursor.execute(
            "INSERT INTO user_activity (user_id, course_id, activity_type) VALUES (?, ?, 'favorite')",
            (session["user_id"], course_id)
        )

        message = "Saved to favorites."

    connection.commit()
    connection.close()

    flash(message, "success")

    return redirect(url_for("course_details", course_id=course_id))


@app.route("/course/<int:course_id>/rate", methods=["POST"])
def rate(course_id):
    if not logged_in():
        flash("Please log in to rate a course.", "error")
        return redirect(url_for("login"))

    try:
        rating = int(request.form.get("rating", 0))
    except ValueError:
        rating = 0

    if rating < 1 or rating > 5:
        flash("Rating must be between 1 and 5.", "error")
        return redirect(url_for("course_details", course_id=course_id))

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO ratings (user_id, course_id, rating)
        VALUES (?, ?, ?)
        ON CONFLICT(user_id, course_id)
        DO UPDATE SET rating = excluded.rating,
                      timestamp = CURRENT_TIMESTAMP
    """, (session["user_id"], course_id, rating))

    cursor.execute(
        "INSERT INTO user_activity (user_id, course_id, activity_type) VALUES (?, ?, 'rate')",
        (session["user_id"], course_id)
    )

    connection.commit()
    connection.close()

    flash("Your rating was saved.", "success")

    return redirect(url_for("course_details", course_id=course_id))


@app.route("/course/<int:course_id>/enroll", methods=["POST"])
def enroll(course_id):
    if not logged_in():
        flash("Please log in to enroll in a course.", "error")
        return redirect(url_for("login"))

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        "SELECT 1 FROM user_activity WHERE user_id = ? AND course_id = ? AND activity_type = 'enroll' LIMIT 1",
        (session["user_id"], course_id)
    )

    if not cursor.fetchone():
        cursor.execute(
            "INSERT INTO user_activity (user_id, course_id, activity_type) VALUES (?, ?, 'enroll')",
            (session["user_id"], course_id)
        )

        connection.commit()
        flash("Course enrolled successfully.", "success")

    else:
        flash("You are already enrolled in this course.", "info")

    connection.close()

    return redirect(url_for("course_details", course_id=course_id))


@app.route("/course/<int:course_id>/complete", methods=["POST"])
def complete(course_id):
    if not logged_in():
        flash("Please log in first.", "error")
        return redirect(url_for("login"))

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        "SELECT 1 FROM user_activity WHERE user_id = ? AND course_id = ? AND activity_type = 'enroll' LIMIT 1",
        (session["user_id"], course_id)
    )

    if not cursor.fetchone():
        flash("Enroll in the course before marking it complete.", "error")

    else:
        cursor.execute(
            "SELECT 1 FROM user_activity WHERE user_id = ? AND course_id = ? AND activity_type = 'complete' LIMIT 1",
            (session["user_id"], course_id)
        )

        if cursor.fetchone():
            flash("Course is already marked as completed.", "info")

        else:
            cursor.execute(
                "INSERT INTO user_activity (user_id, course_id, activity_type) VALUES (?, ?, 'complete')",
                (session["user_id"], course_id)
            )

            connection.commit()
            flash("Congratulations! Course completed.", "success")

    connection.close()

    return redirect(url_for("course_details", course_id=course_id))


@app.route("/dashboard")
def dashboard():
    if not logged_in():
        flash("Please log in to view your dashboard.", "error")
        return redirect(url_for("login"))

    user_id = session["user_id"]

    connection = get_connection()
    cursor = connection.cursor()

    counts = {}

    for activity_type, key in [
        ("view", "viewed"),
        ("enroll", "enrolled"),
        ("complete", "completed"),
        ("favorite", "favorites_count")
    ]:
        cursor.execute(
            "SELECT COUNT(*) AS n FROM user_activity WHERE user_id = ? AND activity_type = ?",
            (user_id, activity_type)
        )

        counts[key] = cursor.fetchone()["n"]

    cursor.execute("""
        SELECT c.*, MAX(ua.timestamp) AS last_view
        FROM user_activity ua
        JOIN courses c ON c.course_id = ua.course_id
        WHERE ua.user_id = ? AND ua.activity_type = 'view'
        GROUP BY c.course_id
        ORDER BY last_view DESC
        LIMIT 6
    """, (user_id,))

    recent = cursor.fetchall()

    cursor.execute("""
        SELECT c.*, MAX(ua.timestamp) AS enrolled_at
        FROM user_activity ua
        JOIN courses c ON c.course_id = ua.course_id
        WHERE ua.user_id = ? AND ua.activity_type = 'enroll'
        GROUP BY c.course_id
        ORDER BY enrolled_at DESC
        LIMIT 6
    """, (user_id,))

    learning = cursor.fetchall()

    cursor.execute("""
        SELECT c.* FROM favorites f
        JOIN courses c ON c.course_id = f.course_id
        WHERE f.user_id = ?
        ORDER BY f.timestamp DESC
        LIMIT 6
    """, (user_id,))

    favorites = cursor.fetchall()

    connection.close()

    recommendations = recommend_courses(user_id, 10)
    interests = get_user_interest_summary(user_id)

    return render_template(
        "dashboard.html",
        **counts,
        recent=recent,
        learning=learning,
        favorites=favorites,
        recommendations=recommendations,
        interests=interests
    )


@app.route("/recommendations")
def recommendations():
    if not logged_in():
        flash("Please log in to see personalized recommendations.", "error")
        return redirect(url_for("login"))

    user_id = session["user_id"]

    recs = recommend_courses(user_id, 10)
    interests = get_user_interest_summary(user_id)

    return render_template(
        "recommendations.html",
        recommendations=recs,
        interests=interests
    )


@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        name = request.form["name"].strip()
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        if not name or not email or len(password) < 6:
            flash(
                "Enter a name, valid email and password of at least 6 characters.",
                "error"
            )
            return render_template("register.html")

        connection = get_connection()
        cursor = connection.cursor()

        try:
            cursor.execute(
                "INSERT INTO users (name, email, password) VALUES (?, ?, ?)",
                (name, email, generate_password_hash(password))
            )

            connection.commit()

            flash("Registration successful. Please log in.", "success")

            return redirect(url_for("login"))

        except Exception:
            flash("That email is already registered.", "error")

        finally:
            connection.close()

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        email = request.form["email"].strip().lower()
        password = request.form["password"]

        connection = get_connection()
        cursor = connection.cursor()

        cursor.execute(
            "SELECT * FROM users WHERE email = ?",
            (email,)
        )

        user = cursor.fetchone()

        connection.close()

        if user and check_password_hash(user["password"], password):
            session["user_id"] = user["user_id"]
            session["user_name"] = user["name"]
            session["is_admin"] = bool(user["is_admin"])

            flash(
                f"Welcome back, {user['name']}!",
                "success"
            )

            return redirect(url_for("dashboard"))

        flash("Invalid email or password.", "error")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()

    flash("You have been logged out.", "info")

    return redirect(url_for("home"))


@app.route("/admin")
def admin():
    if not session.get("is_admin"):
        flash("Admin access only.", "error")
        return redirect(url_for("home"))

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("SELECT * FROM courses ORDER BY course_id DESC")
    all_courses = cursor.fetchall()

    cursor.execute("SELECT COUNT(*) AS n FROM users")
    total_users = cursor.fetchone()["n"]

    cursor.execute("SELECT COUNT(*) AS n FROM courses")
    total_courses = cursor.fetchone()["n"]

    cursor.execute("SELECT COUNT(*) AS n FROM user_activity")
    total_activities = cursor.fetchone()["n"]

    cursor.execute("""
        SELECT ua.activity_id,
               u.name AS user_name,
               c.name AS course_name,
               ua.activity_type,
               ua.timestamp
        FROM user_activity ua
        JOIN users u ON ua.user_id = u.user_id
        JOIN courses c ON ua.course_id = c.course_id
        ORDER BY ua.timestamp DESC
        LIMIT 30
    """)

    activity_logs = cursor.fetchall()

    connection.close()

    return render_template(
        "admin.html",
        courses=all_courses,
        activity_logs=activity_logs,
        total_users=total_users,
        total_courses=total_courses,
        total_activities=total_activities
    )


@app.route("/admin/add_course", methods=["POST"])
def add_course():
    if not session.get("is_admin"):
        flash("Admin access only.", "error")
        return redirect(url_for("home"))

    name = request.form["name"].strip()
    category = request.form["category"].strip()
    description = request.form["description"].strip()
    difficulty = request.form.get("difficulty", "Beginner")
    duration = request.form.get("duration", "Self-paced")
    rating = request.form.get("rating", "4.5")

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO courses
        (name, category, description, difficulty, duration, rating)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        name,
        category,
        description,
        difficulty,
        duration,
        rating
    ))

    connection.commit()
    connection.close()

    flash("Course added successfully.", "success")

    return redirect(url_for("admin"))


@app.route("/admin/delete_course/<int:course_id>", methods=["POST"])
def delete_course(course_id):
    if not session.get("is_admin"):
        flash("Admin access only.", "error")
        return redirect(url_for("home"))

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        "DELETE FROM courses WHERE course_id = ?",
        (course_id,)
    )

    connection.commit()
    connection.close()

    flash("Course deleted.", "success")

    return redirect(url_for("admin"))


if __name__ == "__main__":
    app.run(debug=True)