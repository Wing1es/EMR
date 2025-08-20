# main.py - Electronic Medical Record System Data Model with Flask-SQLAlchemy

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime
import pytz

# Initialize the SQLAlchemy object
db = SQLAlchemy()

# This is a good practice for type hinting built-in types in modern Python
from typing import Optional

# Define the models using db.Model
class Patient(db.Model):
    """
    Represents a patient in the EMR system.
    Note: The original code had a conflicting primary key defined in both the id
    column and the __table_args__. The `id` column is kept as the primary key
    for simplicity and consistency with standard practices.
    """
    __tablename__ = 'patients'
    
    # Primary Key
    id = db.Column(db.Integer, primary_key=True)
    
    # Patient Demographics
    patient_id = db.Column(db.String(50), unique=True, nullable=False)
    version = db.Column(db.Integer, nullable=False, default=1)
    is_active = db.Column(db.Boolean, default=True)
    name = db.Column(db.String(100), nullable=False)
    age = db.Column(db.Integer, nullable=False)
    gender = db.Column(db.String(10), nullable=False)
    phone_number = db.Column(db.String(15))
    email = db.Column(db.String(100))
    
    # Vitals and Health Status
    temperature = db.Column(db.Float)
    bp_systolic = db.Column(db.Integer)
    bp_diastolic = db.Column(db.Integer)
    sugar = db.Column(db.Float)
    height = db.Column(db.Float)
    weight = db.Column(db.Float)
    bmi = db.Column(db.Float)
    temp_status = db.Column(db.String(50))
    bp_status = db.Column(db.String(50))
    sugar_status = db.Column(db.String(50))
    bmi_status = db.Column(db.String(50))
    
    # Timestamps and Records
    record_date = db.Column(db.Date, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    other_vitals = db.Column(db.String(255), nullable=True)

class User(UserMixin, db.Model):
    """
    Represents a user (e.g., doctor, nurse) in the system.
    Inherits from UserMixin for Flask-Login integration.
    """
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), nullable=False, default='user')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def set_password(self, password):
        """Hashes the password and sets it to password_hash."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """Checks the provided password against the hashed password."""
        return check_password_hash(self.password_hash, password)

class AuditLog(db.Model):
    """
    Tracks changes and actions within the system for auditing purposes.
    """
    __tablename__ = 'audit_logs'
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.String(50), nullable=False)
    patient_version = db.Column(db.Integer, nullable=False)
    changed_by = db.Column(db.String(100), nullable=False)
    change_description = db.Column(db.Text, nullable=False)
    # Using a timezone-aware timestamp for clarity and accuracy
    timestamp = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(pytz.timezone('Asia/Kolkata')))

class Prescription(db.Model):
    """
    Represents a prescription record for a patient.
    """
    __tablename__ = 'prescriptions'
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.String(50), db.ForeignKey('patients.patient_id'), nullable=False)
    prescription_text = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Reminder(db.Model):
    """
    Represents a reminder for a patient or user.
    """
    __tablename__ = 'reminders'
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.String(50), db.ForeignKey('patients.patient_id'), nullable=False)
    reminder_text = db.Column(db.Text, nullable=False)
    reminder_date = db.Column(db.DateTime, nullable=False)
    is_active = db.Column(db.Boolean, default=True)


if __name__ == '__main__':
    # Initialize a Flask app for SQLAlchemy to bind to
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///emr.db'
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

    # Bind the db object to the app
    db.init_app(app)

    # This creates the database tables based on the models
    with app.app_context():
        db.create_all()
        print("Database schema created successfully using Flask-SQLAlchemy.")

        # Example of adding a new patient
        # Note: 'patient_id' is now a required, unique string.
        new_patient = Patient(
            patient_id="PAT001", 
            name="Jane Doe", 
            age=34, 
            gender="Female", 
            record_date="2024-01-01",
            phone_number="555-1234",
            email="jane.doe@email.com"
        )
        db.session.add(new_patient)
        db.session.commit()

        print(f"Added patient: {new_patient.name}")

