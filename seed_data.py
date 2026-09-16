from database import get_connection, create_tables
from werkzeug.security import generate_password_hash

COURSES = [
    ("Python for Beginners", "Programming", "Learn Python syntax, variables, functions and problem solving.", "Beginner", "6 hours", 4.8),
    ("Advanced Python", "Programming", "Build stronger Python skills with OOP, modules, exceptions and practical projects.", "Intermediate", "8 hours", 4.7),
    ("Web Development with Flask", "Web Development", "Create dynamic web applications using Python, Flask, routing, templates and APIs.", "Intermediate", "7 hours", 4.6),
    ("Frontend Development", "Web Development", "Build modern interfaces using HTML, CSS, JavaScript, responsive design and browser APIs.", "Beginner", "8 hours", 4.7),
    ("Machine Learning Fundamentals", "AI & ML", "Understand supervised learning, evaluation, classification, regression and common ML algorithms.", "Beginner", "8 hours", 4.8),
    ("Deep Learning Essentials", "AI & ML", "Explore neural networks, training, backpropagation and deep learning concepts.", "Advanced", "10 hours", 4.7),
    ("Natural Language Processing", "AI & ML", "Explore text processing, classification, embeddings and language-model concepts.", "Advanced", "9 hours", 4.6),
    ("Data Science with Python", "Data Science", "Learn data analysis, visualization and practical data science workflows with Python.", "Beginner", "9 hours", 4.9),
    ("SQL and Database Basics", "Data Science", "Learn relational databases, SQL queries, joins and data management.", "Beginner", "5 hours", 4.6),
    ("Data Visualization", "Data Science", "Create clear charts, dashboards and visual stories from datasets.", "Intermediate", "6 hours", 4.6),
    ("UI/UX Design Fundamentals", "Design", "Learn design principles, user flows, wireframes and usability.", "Beginner", "6 hours", 4.5),
    ("Cyber Security Basics", "Cyber Security", "Learn fundamental security concepts, threats, authentication and safe practices.", "Beginner", "6 hours", 4.7),
    ("Ethical Hacking Foundations", "Cyber Security", "Understand ethical security testing, vulnerabilities and defensive practices.", "Intermediate", "8 hours", 4.7),
    ("Cloud Computing Fundamentals", "Cloud Computing", "Understand cloud services, deployment models, virtual machines and core cloud concepts.", "Beginner", "7 hours", 4.6),
    ("Cloud Deployment with Azure", "Cloud Computing", "Deploy web applications on Azure and understand app services, storage and monitoring.", "Intermediate", "8 hours", 4.8),
]


def seed():
    create_tables()
    connection = get_connection()
    cursor = connection.cursor()

    for course in COURSES:
        cursor.execute("SELECT 1 FROM courses WHERE name = ? LIMIT 1", (course[0],))
        if not cursor.fetchone():
            cursor.execute("""
                INSERT INTO courses (name, category, description, difficulty, duration, rating)
                VALUES (?, ?, ?, ?, ?, ?)
            """, course)

    cursor.execute("SELECT 1 FROM users WHERE email = ? LIMIT 1", ("admin@learnhub.com",))
    if not cursor.fetchone():
        cursor.execute("""
            INSERT INTO users (name, email, password, is_admin)
            VALUES (?, ?, ?, 1)
        """, ("Administrator", "admin@learnhub.com", generate_password_hash("admin123")))

    connection.commit()
    connection.close()
    print("Database seeded safely.")


if __name__ == "__main__":
    seed()
