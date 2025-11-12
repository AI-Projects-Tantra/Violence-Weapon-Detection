from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
import os

# Authenticate with Google Drive
gauth = GoogleAuth()
gauth.LocalWebserverAuth()  # Opens a browser for authentication

drive = GoogleDrive(gauth)

def upload_to_drive(file_path):
    file_name = os.path.basename(file_path)
    file_drive = drive.CreateFile({'title': file_name})
    file_drive.SetContentFile(file_path)
    file_drive.Upload()
    file_drive.InsertPermission({'type': 'anyone', 'value': 'anyone', 'role': 'reader'})
    return file_drive['alternateLink']

