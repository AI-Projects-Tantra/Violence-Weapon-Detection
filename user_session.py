import cx_Oracle
from database import get_db_connection

class UserSession:
    """Class to store logged-in user details."""
    def __init__(self):
        self.user_id = None
        self.phone_number = None
        self.email = None

    def load_user_details(self, user_id):
        """Fetch user details from the database when the user logs in."""
        conn = get_db_connection()
        if not conn:
            print("Database connection failed.")
            return

        cursor = conn.cursor()
        cursor.execute("SELECT mobile_number, email FROM users WHERE id = :1", (user_id,))
        user_data = cursor.fetchone()
        conn.close()

        if user_data:
            self.user_id = user_id
            self.phone_number, self.email = user_data
            print(f"User details loaded: Phone - {self.phone_number}, Email - {self.email}")
        else:
            print("Error: User not found in the database")

# Create a global session object
user_session = UserSession()
