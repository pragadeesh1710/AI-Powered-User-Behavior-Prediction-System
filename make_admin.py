from database import get_connection, create_tables

EMAIL = "admin@learnhub.com"


def make_admin():
    create_tables()
    connection = get_connection()
    cursor = connection.cursor()
    cursor.execute("UPDATE users SET is_admin = 1 WHERE email = ?", (EMAIL,))
    connection.commit()
    print(f"Admin enabled for {EMAIL}.")
    connection.close()


if __name__ == "__main__":
    make_admin()
