from PyQt5.QtWidgets import QMainWindow, QApplication
from PyQt5.uic import loadUi
from PyQt5.QtCore import QThread, Qt, pyqtSignal, pyqtSlot
from PyQt5.QtGui import QImage, QPixmap
import torch
import cv2
import numpy as np
import time
import os
from tensorflow.keras.models import load_model
from tensorflow.keras.applications import ResNet50
from tensorflow.keras.applications.resnet50 import preprocess_input
from tensorflow.keras.models import Model
from ultralytics import YOLO
import warnings
import datetime
import sys
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
from drive_upload import upload_to_drive
from twilio.rest import Client  # Twilio for SMS
import smtplib  # SMTP for Email
from email.message import EmailMessage
from user_session import user_session
from concurrent.futures import ThreadPoolExecutor



# Suppress TensorFlow warnings
warnings.filterwarnings("ignore", category=UserWarning, module='tensorflow')

# Twilio Configuration
TWILIO_SID = "ur id"
TWILIO_AUTH_TOKEN = "ur token"
TWILIO_PHONE_NUMBER = "ur no."

# Email Configuration
SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 587
EMAIL_SENDER = "ur email"
EMAIL_PASSWORD = "ur email password"

class Detection(QThread):
    changePixmap = pyqtSignal(QImage)

    def __init__(self):
        super(Detection, self).__init__()
        self.running = True
        self.recording = False
        self.video_writer = None
        self.executor = ThreadPoolExecutor(max_workers=4)

        # Load YOLO weapon detection model
        self.custom_model = YOLO(r'C:\Proj6 (1)\Client Side\Weights\best(1).pt')

        # Load BiLSTM-ResNet model that takes raw image sequences
        self.bilstm_model = load_model(r"C:\Users\23gsa\Downloads\BILSTM_RESNET_MODEL.h5", compile=False)

        # Frame sequence parameters
        self.IMAGE_HEIGHT, self.IMAGE_WIDTH = 64, 64
        self.SEQUENCE_LENGTH = 16
        self.frame_buffer = []

        self.violence_frames = []
        self.non_violence_frames = []
        self.min_recording_duration = 20
        self.pre_violence_duration = 10
        self.CLASSES_LIST = ["NonViolence", "Violence"]

    def send_sms_alert(self, message):
        """Send SMS notification using Twilio to logged-in user."""
        if not user_session.phone_number:
            print("❌ No recipient phone number found. Please log in first.")
            return

        recipient_number = user_session.phone_number.strip()

        # If the number is 10 digits (Indian mobile), prepend "+91"
        if recipient_number.isdigit() and len(recipient_number) == 10:
            recipient_number = "+91" + recipient_number
        elif not recipient_number.startswith("+"):
            print("❌ Invalid phone number format.")
            return

        client = Client(TWILIO_SID, TWILIO_AUTH_TOKEN)
        try:
            client.messages.create(
                body=message,
                from_=TWILIO_PHONE_NUMBER,
                to=recipient_number  # Updated number with +91 if needed
            )
            print(f"✅ SMS notification sent successfully to {recipient_number}")
        except Exception as e:
            print(f"❌ Failed to send SMS: {e}")


    def send_email_alert(self, subject, message):
        """Send Email notification using SMTP to logged-in user."""
        if not user_session.email:
            print("❌ No recipient email found. Please log in first.")
            return

        try:
            msg = EmailMessage()
            msg.set_content(message)
            msg["Subject"] = subject
            msg["From"] = EMAIL_SENDER
            msg["To"] = user_session.email  # Use logged-in user's email

            server = smtplib.SMTP(SMTP_SERVER, SMTP_PORT)
            server.starttls()
            server.login(EMAIL_SENDER, EMAIL_PASSWORD)
            server.send_message(msg)
            server.quit()

            print("✅ Email notification sent successfully.")
        except Exception as e:
            print(f"❌ Failed to send email: {e}")

    def preprocess_frame(self, frame):
        resized = cv2.resize(frame, (self.IMAGE_WIDTH, self.IMAGE_HEIGHT))
        normalized = resized / 255.0
        return normalized

    def extract_features_from_frames(self, frame, num_frames=16, target_size=(224, 224)):
        frames = np.array([self.preprocess_frame(frame, target_size) for _ in range(num_frames)])
        features = self.feature_extractor.predict(frames)
        features = np.expand_dims(features, axis=-1)
        return np.expand_dims(features, axis=0)

    def run(self):
        cap = cv2.VideoCapture(0)
        if not cap.isOpened():
            print("Error: Could not open video stream.")
            return

        fps = cap.get(cv2.CAP_PROP_FPS)
        if fps <= 0:
            fps = 30

        while self.running:
            ret, frame = cap.read()
            if not ret:
                print("Error: Failed to capture frame.")
                continue

            boxes, confidences, labels = [], [], []
            results_custom = self.custom_model(frame)
            pred_custom = results_custom[0].boxes
            weapon_detected = False

            for box in pred_custom:
                x1, y1, x2, y2 = map(int, box.xyxy[0].tolist())
                confidence = float(box.conf[0])
                class_id = int(box.cls[0])
                label = self.custom_model.names[class_id]

                if confidence > 0.3:
                    boxes.append([x1, y1, x2 - x1, y2 - y1])
                    confidences.append(confidence)
                    labels.append("weapon")
                    if label.lower() in ["weapon", "weapons"]:
                        weapon_detected = True

            self.draw_bounding_boxes(frame, boxes, labels, confidences)
            if weapon_detected:
                self.save_detection(frame)

            # Prepare frame for BiLSTM model
            processed_frame = self.preprocess_frame(frame)
            self.frame_buffer.append(processed_frame)
            if len(self.frame_buffer) > self.SEQUENCE_LENGTH:
                self.frame_buffer.pop(0)

            if len(self.frame_buffer) == self.SEQUENCE_LENGTH:
                input_sequence = np.expand_dims(np.array(self.frame_buffer), axis=0)
                prediction = self.bilstm_model.predict(input_sequence)[0]
                predicted_label = np.argmax(prediction)
                predicted_class = self.CLASSES_LIST[predicted_label]
                confidence = prediction[predicted_label]

                label = predicted_class
                color = (0, 0, 255) if label == "Violence" else (0, 255, 0)

                cv2.putText(frame, f"{label} ({confidence:.2f})", (50, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, color, 2)

                if label == "Violence":
                    if not self.recording:
                        self.start_recording(frame, fps)
                    self.violence_frames.append(frame)
                    if self.video_writer:
                        self.video_writer.write(frame)
                elif self.recording:
                    elapsed_time = time.time() - self.violence_start_time
                    if elapsed_time >= self.min_recording_duration:
                        self.stop_recording()
                elif not self.recording:
                    self.non_violence_frames.append(frame)

            rgbImage = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            bytesPerLine = 3 * frame.shape[1]
            convertToQtFormat = QImage(rgbImage.data, frame.shape[1], frame.shape[0], bytesPerLine, QImage.Format_RGB888)
            self.changePixmap.emit(convertToQtFormat)

        cap.release()

    def start_recording(self, frame, fps):
        self.recording = True
        self.violence_start_time = time.time()
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        if not os.path.exists("saved_videos"):
            os.makedirs("saved_videos")

        self.video_filename = os.path.join("saved_videos", f"violence_recording_{timestamp}.mp4")
        self.frame_size = (frame.shape[1], frame.shape[0])

        self.video_writer = cv2.VideoWriter(self.video_filename, cv2.VideoWriter_fourcc(*'mp4v'), fps, self.frame_size)

        print(f"Recording started: {self.video_filename} at {fps} fps")

        for pre_violence_frame in self.non_violence_frames[-int(self.pre_violence_duration * fps):]:
            self.video_writer.write(pre_violence_frame)

        self.non_violence_frames = []

    def stop_recording(self):
        if self.video_writer is not None:
            self.video_writer.release()
            self.video_writer = None
            print(f"Recording stopped. Video saved as: {self.video_filename}")

            if os.path.exists(self.video_filename):
                print(f"Uploading {self.video_filename} to Google Drive asynchronously...")

                # Run upload and notifications asynchronously
                self.executor.submit(self.handle_violence_alert, self.video_filename)
            else:
                print("Error: Video file not found for upload.")

        self.recording = False
        self.violence_frames = []

    def handle_violence_alert(self, filename):
        try:
            drive_link = upload_to_drive(filename)
            print(f"✅ Video uploaded to Google Drive: {drive_link}")
            alert_message = f"Violence detected!\nView video: {drive_link}"
            self.send_sms_alert(alert_message)
            self.send_email_alert("Violence Detected Alert", alert_message)
        except Exception as e:
            print(f"❌ Error in handle_violence_alert: {e}")
        finally:
            self.recording = False
            self.violence_frames = []

    def draw_bounding_boxes(self, frame, boxes, labels, confidences):
        for i, (x, y, w, h) in enumerate(boxes):
            label = f"{labels[i]}: {confidences[i]:.2f}"
            cv2.rectangle(frame, (x, y), (x + w, y + h), (0, 255, 0), 3)
            cv2.putText(frame, label, (x, y - 10), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

    def save_detection(self, frame):
        if not os.path.exists("saved_frame"):
            os.makedirs("saved_frame")

        frame_filename = os.path.join("saved_frame", f"frame_{int(time.time())}.jpg")
        cv2.imwrite(frame_filename, frame)
        print(f'Frame Saved: {frame_filename}')

        # Run upload and notifications asynchronously
        self.executor.submit(self.handle_weapon_alert, frame_filename)

    def handle_weapon_alert(self, filename):
        try:
            drive_link = upload_to_drive(filename)
            print(f"Frame uploaded to Google Drive: {drive_link}")
            alert_message = f"Weapon detected!\nView frame: {drive_link}"
            self.send_sms_alert(alert_message)
            self.send_email_alert("Weapon Detected Alert", alert_message)
        except Exception as e:
            print(f"❌ Error in handle_weapon_alert: {e}")

    def stop(self):
        self.running = False
        self.executor.shutdown(wait=False)  # Non-blocking shutdown