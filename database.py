import cx_Oracle

# Database connection function
def get_db_connection():
    try:
        dsn = cx_Oracle.makedsn("localhost", 1521, service_name="XEPDB1")
        conn = cx_Oracle.connect(user="username", password="password", dsn=dsn)
        print("Connected as:", conn.username)
        return conn
    except cx_Oracle.DatabaseError as e:
        print("Database connection failed:", e)
        return None


# Register user (without password hashing)
def register_user(username, password, mobile, email):
    conn = get_db_connection()
    if not conn:
        return False
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM users WHERE username = :1", (username,))
    if cursor.fetchone()[0] > 0:
        print("User already registered.")
        conn.close()
        return False

    cursor.execute('SELECT COUNT(*) FROM users WHERE UPPER(email) = UPPER(:1)', (email,))
    if cursor.fetchone()[0] > 0:
        print("Email already in use.")
        conn.close()
        return False

    cursor.execute("SELECT COUNT(*) FROM users WHERE mobile_number = :1", (mobile,))
    if cursor.fetchone()[0] > 0:
        print("Mobile number already in use.")
        conn.close()
        return False

    # Insert new user
    cursor.execute("INSERT INTO users (username, password, mobile_number, email) VALUES (:1, :2, :3, :4)", 
                   (username, password, mobile, email))
    conn.commit()
    conn.close()
    print("User registered successfully.")
    return True

# Verify user login
def verify_user(username, password):
    """Authenticate user and return user ID if valid."""
    conn = get_db_connection()
    if not conn:
        return None  # Return None if connection fails

    cursor = conn.cursor()
    cursor.execute("SELECT table_name FROM user_tables")
    print("Available tables:", [row[0] for row in cursor.fetchall()])
    cursor.execute("SELECT id FROM users WHERE username = :1 AND password = :2", (username, password))
    user = cursor.fetchone()

    conn.close()
    return user[0] if user else None  # Return user ID if found, else None
