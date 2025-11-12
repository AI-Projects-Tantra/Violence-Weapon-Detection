from PyQt5.QtWidgets import QMainWindow, QMessageBox
from PyQt5.uic import loadUi
from settings_window import SettingsWindow
from database import verify_user
from register_window import RegisterWindow
from user_session import user_session  # Import UserSession object

class LoginWindow(QMainWindow):
    def __init__(self):
        super(LoginWindow, self).__init__()
        loadUi('UI/login_window.ui', self)

        self.register_button.clicked.connect(self.go_to_register_page)
        self.login_button.clicked.connect(self.authenticate_user)

        self.show()

    def go_to_register_page(self):
        self.register_window = RegisterWindow()
        self.register_window.show()

    def authenticate_user(self):
        username = self.username_input.text()
        password = self.password_input.text()

        user_id = verify_user(username, password)  # Get user ID from database

        if user_id:
            QMessageBox.information(self, "Login Successful", "Welcome!")
            
            # Load phone number & email into session
            user_session.load_user_details(user_id)
            
            self.settings_window = SettingsWindow()
            self.settings_window.displayInfo()
            self.close()
        else:
            QMessageBox.warning(self, "Login Failed", "Invalid username or password!")