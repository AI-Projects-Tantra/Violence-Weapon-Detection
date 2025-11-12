from PyQt5.QtWidgets import QMainWindow, QMessageBox
from PyQt5.uic import loadUi
from database import register_user

class RegisterWindow(QMainWindow):
    def __init__(self):
        super(RegisterWindow, self).__init__()
        loadUi('UI/register_window.ui', self)

        self.register_button.clicked.connect(self.create_account)

    def create_account(self):
        username = self.username_input.text()
        password = self.password_input.text()  # Plain text password (not secure)
        mobile_number = self.mobile_input.text()  
        email = self.email_input.text()  

        if not username or not password or not mobile_number or not email:
            QMessageBox.warning(self, "Error", "All fields are required!")
            return

        if register_user(username, password, mobile_number, email):  # Storing plain password
            QMessageBox.information(self, "Success", "Registration Successful!")
            self.close()
        else:
            QMessageBox.warning(self, "Error", "Username, Mobile, or Email already exists!")
