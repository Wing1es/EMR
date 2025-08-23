import os
from flask import (Flask, render_template, request, redirect, session, 
                    url_for, flash, jsonify, Response)
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import or_
import pytz
from werkzeug.security import generate_password_hash, check_password_hash

from datetime import datetime, timedelta, time, timezone
from functools import wraps
import uuid
import csv
from io import StringIO
import json
from collections import Counter, OrderedDict
import math

# --- AI IMPORTS AND SETUP ---
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
# --- END AI SETUP ---

# --- DATABASE SETUP ---
app = Flask(__name__)
app.secret_key = "a_super_secret_and_random_key_for_health_app_sessions"
app.config['SQLALCHEMY_DATABASE_URI'] = 'postgresql://postgres:rishi@localhost:5432/health_app_db'

app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
# --- END DATABASE SETUP ---

# --- AI CONFIGURATION ---
api_key = "AIzaSyBLuOdTsiCQQDoHEpk2GCvBNBSKkqTKt48"
if not api_key:
    print("CRITICAL WARNING: GEMINI_API_KEY environment variable not found.")
else:
    try:
        genai.configure(api_key=api_key)
    except Exception as e:
        print(f"Error configuring Gemini API: {e}")
# --- END AI CONFIGURATION ---

# ---SQLALCHEMY DATABASE MODELS (UPDATED) ---
class User(db.Model):
    
    """
    User database model.
    The `User` model is now defined here, resolving the import issue.
    """
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(20), unique=True, nullable=False)
    # The password_hash column length has been increased to 255 to prevent truncation errors.
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False)
    department = db.Column(db.String(50), nullable=True) # New field
    is_active = db.Column(db.Boolean, nullable=False, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"User('{self.username}', '{self.role}')"

class Patient(db.Model):
    __tablename__ = 'patients'
    id = db.Column(db.Integer, primary_key=True)
    uhid = db.Column(db.String(20), index=True, nullable=False)

    # Patient Information
    name = db.Column(db.String(255), nullable=False)
    age = db.Column(db.Integer)
    gender = db.Column(db.String(20))
    phone_number = db.Column(db.String(50), nullable=True)
    email = db.Column(db.String(255), nullable=True)
    address = db.Column(db.Text, nullable=True)  # New column for address

    # Vital Signs
    temperature = db.Column(db.Float)
    bp_systolic = db.Column(db.Integer)
    bp_diastolic = db.Column(db.Integer)
    sugar = db.Column(db.Integer)
    height = db.Column(db.Float)
    weight = db.Column(db.Float)

    # Lifestyle
    smoking_status = db.Column(db.String(50), nullable=True) # New column
    alcohol_frequency = db.Column(db.String(50), nullable=True) # New column
    physical_activity = db.Column(db.String(50), nullable=True) # New column
    diet_type = db.Column(db.String(50), nullable=True) # New column

    # Past History
    chronic_conditions = db.Column(db.Text, nullable=True) # New column
    current_medications = db.Column(db.Text, nullable=True) # New column
    allergies = db.Column(db.Text, nullable=True) # New column

    # Status Fields
    bmi = db.Column(db.Float)
    temp_status = db.Column(db.String(20))
    bp_status = db.Column(db.String(20))
    sugar_status = db.Column(db.String(20))
    bmi_status = db.Column(db.String(20))

    # Record Metadata
    record_date = db.Column(db.Date)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

    # Existing metadata
    version = db.Column(db.Integer, nullable=False, default=1)
    is_active = db.Column(db.Boolean, default=True, nullable=False, index=True)

    prescriptions = db.relationship(
        'Prescription',
        backref='patient',
        lazy=True,
        cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"Patient('{self.name}', '{self.uhid}')"


class Prescription(db.Model):
    __tablename__ = 'prescriptions'
    # Corrected `Integer` to `db.Integer` and so on
    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patients.id'), nullable=False)
    reminder_type = db.Column(db.String(50), nullable=False, default='Medication')
    doctor_name = db.Column(db.String(100), nullable=True)
    medication_name = db.Column(db.String(150), nullable=True)
    frequency = db.Column(db.Integer, nullable=True)
    duration = db.Column(db.Integer, nullable=True)
    start_date = db.Column(db.Date, nullable=True)
    follow_up_datetime = db.Column(db.DateTime, nullable=True)
    special_note = db.Column(db.Text, nullable=True)
    # Corrected method to datetime.now(timezone.utc)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    reminders = db.relationship('Reminder', backref='prescription', lazy='dynamic', cascade="all, delete-orphan")

class Reminder(db.Model):
    __tablename__ = 'reminders'
    # Corrected `Integer` to `db.Integer` and so on
    id = db.Column(db.Integer, primary_key=True)
    prescription_id = db.Column(db.Integer, db.ForeignKey('prescriptions.id'), nullable=False)
    reminder_time = db.Column(db.DateTime, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='Scheduled')

class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    # Corrected `Integer` to `db.Integer` and so on
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    username = db.Column(db.String(80))
    event_type = db.Column(db.String(50))
    event_details = db.Column(db.Text)
    # Corrected method to datetime.now(timezone.utc)
    timestamp = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    session_id = db.Column(db.String(100))
    ip_address = db.Column(db.String(45))
    changed_from = db.Column(db.Text, nullable=True)
    changed_to = db.Column(db.Text, nullable=True)
# --- END MODELS ---

# --- TIMEZONE CONVERSION FILTERS ---
@app.template_filter('to_ist_datetime')
def to_ist_datetime_filter(utc_dt):
    if utc_dt is None:
        return ""
    ist_dt = utc_dt + timedelta(hours=5, minutes=30)
    return ist_dt.strftime('%Y-%m-%d %I:%M %p')

@app.template_filter('to_ist_time')
def to_ist_time_filter(utc_dt):
    if utc_dt is None:
        return ""
    ist_dt = utc_dt + timedelta(hours=5, minutes=30)
    return ist_dt.strftime('%I:%M %p')

# --- CUSTOM PAGINATION HELPER ---
class CustomPagination:
    def __init__(self, items, page, per_page, total):
        self.items = items
        self.page = page
        self.per_page = per_page
        self.total = total
        self.pages = int(math.ceil(total / float(per_page)))

    @property
    def has_prev(self):
        return self.page > 1

    @property
    def has_next(self):
        return self.page < self.pages

    @property
    def prev_num(self):
        return self.page - 1 if self.has_prev else None

    @property
    def next_num(self):
        return self.page + 1 if self.has_next else None

    def iter_pages(self, left_edge=2, left_current=2, right_current=5, right_edge=2):
        last = 0
        for num in range(1, self.pages + 1):
            if num <= left_edge or \
               (self.page - left_current - 1 < num < self.page + right_current) or \
               num > self.pages - right_edge:
                if last + 1 != num:
                    yield None
                yield num
                last = num

# --- HELPER FUNCTIONS ---
def generate_uhid():
    year = datetime.now().year
    prefix = f"HC{year}-"
    last_patient = Patient.query.filter(Patient.uhid.startswith(prefix)).order_by(Patient.uhid.desc()).first()
    if last_patient:
        try:
            last_seq = int(last_patient.uhid.split('-')[1])
            new_seq = last_seq + 1
        except (ValueError, IndexError):
            new_seq = 1
    else:
        new_seq = 1
    return f"{prefix}{new_seq:05d}"

def safe_convert(value_str, target_type, field_name):
    stripped_value = str(value_str).strip()
    if not stripped_value:
        if field_name in ["phone_number", "email", "age", "height", "weight", "temperature", "bp_systolic", "bp_diastolic", "sugar"]:
            return None
    try:
        return target_type(stripped_value)
    except (ValueError, TypeError):
        raise ValueError(f"'{stripped_value}' is not a valid {target_type.__name__} for {field_name}.")

def get_status(temp, bp_sys, bp_dia, sugar, bmi):
    temp_status = "Normal" if temp is not None and 97 <= temp <= 99 else "Abnormal"
    bp_status = "Normal" if bp_sys is not None and bp_dia is not None and 90 <= bp_sys <= 120 and 60 <= bp_dia <= 80 else "Abnormal"
    sugar_status = "Normal" if sugar is not None and 80 <= sugar <= 110 else "Abnormal"
    bmi_status = "Normal" if bmi is not None and 18.5 <= bmi <= 24.9 else "Abnormal"
    return temp_status, bp_status, sugar_status, bmi_status

def log_audit_event(event_type, event_details=None, changed_from=None, changed_to=None):
    try:
        user_id = session.get('user_id')
        username = session.get('username', 'Anonymous')
        session_id = session.get('session_id', 'N/A')
        ip_address = request.remote_addr
        log_entry = AuditLog(
            user_id=user_id,
            username=username,
            event_type=event_type,
            event_details=json.dumps(event_details) if event_details is not None else None,
            session_id=session_id,
            ip_address=ip_address,
            changed_from=json.dumps(changed_from, indent=2) if changed_from else None,
            changed_to=json.dumps(changed_to, indent=2) if changed_to else None
        )
        db.session.add(log_entry)
        db.session.commit()
    except Exception as e:
        print(f"Error logging audit event: {e}")
        db.session.rollback()

def parse_other_vitals(form_data):
    """
    Parses dynamic 'Other Vitals' fields from form data.
    Returns a JSON string of the key-value pairs.
    """
    other_vitals_dict = {}
    vital_counter = 1
    while True:
        vital_name_key = f'vital_name_{vital_counter}'
        vital_value_key = f'vital_value_{vital_counter}'
        
        vital_name = form_data.get(vital_name_key, '').strip()
        vital_value = form_data.get(vital_value_key, '').strip()

        if not vital_name or not vital_value:
            # Stop when we no longer find a pair of vital name and value
            break
        
        other_vitals_dict[vital_name] = vital_value
        vital_counter += 1
    
    return json.dumps(other_vitals_dict) if other_vitals_dict else None

# --- DECORATORS ---
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("logged_in"):
            flash("Please log in to access this page.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get("logged_in"):
            flash("Please log in to access this page.", "warning")
            return redirect(url_for("login"))
        if session.get("role") != "admin":
            log_audit_event('UNAUTHORIZED_ACCESS', f"User '{session.get('username')}' attempted to access admin page: {request.path}")
            flash("You do not have permission to access this page.", "error")
            return redirect(url_for("dashboard"))
        return f(*args, **kwargs)
    return decorated_function

# --- CORE & AUTH ROUTES ---
@app.route('/')
def home():
    return render_template('home.html')

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        userid = request.form["userid"].strip()
        password = request.form["password"].strip()
        user = User.query.filter_by(username=userid).first()
        if user and check_password_hash(user.password_hash, password):
            session["logged_in"] = True
            session["user_id"] = user.id
            session["username"] = user.username
            session["role"] = user.role
            session["session_id"] = str(uuid.uuid4())
            log_audit_event('LOGIN_SUCCESS', f"User '{userid}' logged in successfully.")
            flash(f"Logged in successfully as {user.username}!", "success")
            return redirect(url_for("dashboard"))
        else:
            log_audit_event('LOGIN_FAILURE', f"Failed login attempt for username '{userid}'.")
            flash("Invalid User ID or Password", "error")
    return render_template("home.html")

@app.route("/logout")
@login_required
def logout():
    log_audit_event('LOGOUT', f"User '{session.get('username')}' logged out.")
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for("login"))

# --- DASHBOARD ROUTE ---
# Assuming this is part of your main.py
# --- DASHBOARD ROUTE ---
@app.route('/dashboard')
@login_required
def dashboard():
    """
    Displays the user dashboard with key statistics.
    """
    try:
        # Fetch the total count of distinct patients.
        total_patients_uhids = db.session.query(Patient.uhid).distinct().count()

        # Count total active patients.
        total_active_patients = Patient.query.filter_by(is_active=True).distinct(Patient.uhid).count()
        
        # Count total prescriptions.
        total_prescriptions = Prescription.query.count()

        # Count patients with at least one abnormal vital sign.
        abnormal_vitals_count = Patient.query.filter(
            Patient.is_active == True,
            (Patient.temp_status == 'Abnormal') |
            (Patient.bp_status == 'Abnormal') |
            (Patient.sugar_status == 'Abnormal') |
            (Patient.bmi_status == 'Abnormal')
        ).distinct(Patient.uhid).count()

        # Group all stats into a dictionary named 'stats'.
        stats = {
            'total_patients': total_patients_uhids,
            'total_active_patients': total_active_patients,
            'total_prescriptions': total_prescriptions,
            'abnormal_vitals_count': abnormal_vitals_count
        }

        # --- FIX: Pass user_role and username to the template ---
        return render_template('dashboard.html', stats=stats, username=session.get('username'), user_role=session.get('role'))

    except Exception as e:
        # Log the error for debugging
        app.logger.error(f"Error in dashboard: {e}")
        flash("An error occurred while loading the dashboard. Please try again later.", "error")
        return redirect(url_for("records"))



# --- AI DETECTOR ROUTE ---
@app.route('/detect', methods=['POST'])
@login_required
def detect_conditions():
    input_text = request.form.get('text', '')
    image_file = request.files.get('image')

    if not input_text and not image_file:
        return jsonify({'error': 'No text or image provided for analysis.'}), 400

    prompt = f"""
    You are a clinical decision support assistant for trained healthcare workers.
    Based on the information below, provide a structured clinical analysis.
    Format the output using simple HTML tags (<h4>, <ul>, <li>, <p>, <b>, <i>).

    *Input Data:*
    {input_text}

    *Analysis Structure:*

    <h4><i class="fas fa-exclamation-triangle" style="color: #EF4444;"></i> 1. Red Flags / Urgent Actions</h4>
    <p>List any critical signs that warrant immediate escalation (e.g., signs of sepsis, severe respiratory distress). If none, state "No immediate red flags identified."</p>

    <h4><i class="fas fa-stethoscope"></i> 2. Top Potential Conditions</h4>
    <ul>
        <li>List potential conditions, from most to least likely, with a confidence level (High, Medium, Low). For example: <b>Viral URI</b> (High Confidence)</li>
    </ul>

    <h4><i class="fas fa-question-circle"></i> 3. Key Questions to Ask Patient</h4>
    <ul>
        <li>List 3-4 critical follow-up questions to ask.</li>
    </ul>

    <h4><i class="fas fa-vials"></i> 4. Recommended Initial Investigations</h4>
    <ul>
        <li>Suggest relevant lab tests or imaging (e.g., CBC, Chest X-ray).</li>
    </ul>

    <p><br><em><b>Disclaimer:</b> This AI analysis supports clinical judgment and is not a substitute for a professional medical diagnosis.</em></p>
    """

    try:
        model = genai.GenerativeModel('gemini-1.5-flash')
        content_parts = [prompt]

        if image_file:
            if image_file.mimetype not in ['image/jpeg', 'image/png']:
                return jsonify({'error': 'Unsupported image format. Please use JPEG or PNG.'}), 400
            image_part = {"mime_type": image_file.mimetype, "data": image_file.read()}
            content_parts.append(image_part)

        response = model.generate_content(content_parts)
        
        ai_response_text = response.text.strip()
        if ai_response_text.startswith("```html"):
            ai_response_text = ai_response_text[len("```html"):].strip()
        if ai_response_text.endswith("```"):
            ai_response_text = ai_response_text[:-len("```")].strip()
        
        if ai_response_text.startswith("<html>"):
            ai_response_text = ai_response_text[len("<html>"):].strip()
        if ai_response_text.endswith("</html>"):
            ai_response_text = ai_response_text[:-len("</html>")].strip()

        log_audit_event('AI_ANALYSIS', f"Performed AI analysis on text: '{input_text[:50]}...'")
        return jsonify({'conditions': ai_response_text})

    except Exception as e:
        print(f"An error occurred during Gemini API call: {e}")
        log_audit_event('AI_ANALYSIS_FAILED', f"AI analysis failed: {e}")
        return jsonify({'error': f'The AI model could not be reached. Please check the API key and server logs.'}), 500

@app.route("/patient_entry", methods=["GET", "POST"])
@login_required
def patient_entry():
    if request.method == "POST":
        try:
            # ✅ UHID is already generated in GET, also confirm here before saving
            new_uhid = request.form.get("uhid")

            # Patient Information
            name = request.form["name"].strip()
            age = safe_convert(request.form.get("age", ""), int, "Age")
            gender = request.form["gender"].strip()
            phone_number = request.form.get('phone_number', '').strip()
            email = request.form.get('email', '').strip()
            address = request.form.get('address', '').strip() # New field

            # Vital Signs
            temp = safe_convert(request.form.get("temp", ""), float, "Temperature")
            bp_sys = safe_convert(request.form.get("bp_sys", ""), int, "Systolic BP")
            bp_dia = safe_convert(request.form.get("bp_dia", ""), int, "Diastolic BP")
            sugar = safe_convert(request.form.get("sugar", ""), int, "Blood Sugar")
            height = safe_convert(request.form.get("height", ""), float, "Height")
            weight = safe_convert(request.form.get("weight", ""), float, "Weight")
            record_date = request.form["record_date"]

            # Lifestyle fields (New)
            smoking_status = request.form.get('smoking_status', '').strip()
            alcohol_frequency = request.form.get('alcohol_frequency', '').strip()
            physical_activity = request.form.get('physical_activity', '').strip()
            diet_type = request.form.get('diet_type', '').strip()

            # Past History fields (New)
            chronic_conditions = request.form.get('chronic_conditions', '').strip()
            current_medications = request.form.get('current_medications', '').strip()
            allergies = request.form.get('allergies', '').strip()

            if not name:
                raise ValueError("Name cannot be empty.")
            if not gender:
                raise ValueError("Gender cannot be empty.")

            record_date_dt = datetime.strptime(record_date, '%Y-%m-%d').date()

            bmi = round(weight / ((height / 100) ** 2), 2) if height and weight and height > 0 else 0
            temp_status, bp_status, sugar_status, bmi_status = get_status(temp, bp_sys, bp_dia, sugar, bmi)

            new_patient = Patient(
                uhid=new_uhid,  # ✅ Save UHID
                name=name,
                age=age,
                gender=gender,
                phone_number=phone_number,
                email=email,
                address=address, # Added new address field
                temperature=temp,
                bp_systolic=bp_sys,
                bp_diastolic=bp_dia,
                sugar=sugar,
                height=height,
                weight=weight,
                smoking_status=smoking_status, # Added new lifestyle fields
                alcohol_frequency=alcohol_frequency,
                physical_activity=physical_activity,
                diet_type=diet_type,
                chronic_conditions=chronic_conditions, # Added new past history fields
                current_medications=current_medications,
                allergies=allergies,
                bmi=bmi,
                temp_status=temp_status,
                bp_status=bp_status,
                sugar_status=sugar_status,
                bmi_status=bmi_status,
                record_date=record_date_dt,
                version=1,
                is_active=True,
                # Removed 'other_vitals' as it's not in the new model
            )
            db.session.add(new_patient)
            db.session.commit()

            log_audit_event('PATIENT_CREATED', f"Created new patient record '{new_patient.name}' (UHID: {new_patient.uhid}).")
            flash(f"Patient record saved successfully! UHID: {new_patient.uhid}", "success")
            return redirect(url_for("records"))

        except (ValueError, Exception) as e:
            db.session.rollback()
            flash(str(e), "error")

    else:
        # ✅ Generate next UHID in GET request
        last_patient = Patient.query.order_by(Patient.id.desc()).first()
        if last_patient and last_patient.uhid:
            last_number = int(last_patient.uhid.replace("UH", ""))
            new_number = last_number + 1
        else:
            new_number = 1
        new_uhid = f"UH{new_number:04d}"  # UH0001, UH0002, ...

        return render_template("patient_entry.html", uhid=new_uhid)




@app.route("/records")
@login_required
def records():
    query = Patient.query.filter_by(is_active=True)
    rows = query.order_by(Patient.uhid.asc()).all()

    log_audit_event('VIEW_RECORDS', "Viewed active patient records.")
    return render_template("records.html", rows=rows)

# The Flask route to handle patient record editing.
# This function handles both showing the form (GET) and processing the update (POST).
@app.route("/edit/<string:record_id>", methods=["GET", "POST"])
@login_required
def edit_patient(record_id):
    """
    Handles the editing of an existing patient record.
    If the request method is POST, a new version of the record is created.
    """
    old_record = db.session.query(Patient).filter_by(uhid=record_id, is_active=True).first()
    if not old_record:
        # Flash an error and redirect if the record doesn't exist.
        flash("Original record not found.", "error")
        return redirect(url_for('records'))

    if request.method == "POST":
        try:
            # Capture the current state of the record before changes for auditing.
            changed_from = {col.name: getattr(old_record, col.name) for col in old_record.__table__.columns if not col.name.startswith('_')}

            # Deactivate the old record to maintain a history.
            old_record.is_active = False

            # Determine the new version number.
            new_version = old_record.version + 1

            # Get data from the form.
            # Patient Information
            name = request.form["name"].strip()
            age = safe_convert(request.form.get("age", ""), int, "Age")
            gender = request.form["gender"].strip()
            phone_number = request.form.get('phone_number', '').strip()
            email = request.form.get('email', '').strip()
            address = request.form.get('address', '').strip() # New column

            # Vital Signs
            temp = safe_convert(request.form.get("temp", ""), float, "Temperature")
            bp_sys = safe_convert(request.form.get("bp_sys", ""), int, "Systolic BP")
            bp_dia = safe_convert(request.form.get("bp_dia", ""), int, "Diastolic BP")
            sugar = safe_convert(request.form.get("sugar", ""), int, "Blood Sugar")
            height = safe_convert(request.form.get("height", ""), float, "Height")
            weight = safe_convert(request.form.get("weight", ""), float, "Weight")

            # Lifestyle (New columns)
            smoking_status = request.form.get('smoking_status', '').strip()
            alcohol_frequency = request.form.get('alcohol_frequency', '').strip()
            physical_activity = request.form.get('physical_activity', '').strip()
            diet_type = request.form.get('diet_type', '').strip()

            # Past History (New columns)
            chronic_conditions = request.form.get('chronic_conditions', '').strip()
            current_medications = request.form.get('current_medications', '').strip()
            allergies = request.form.get('allergies', '').strip()

            # Convert date string to a date object.
            record_date_str = request.form["record_date"]
            record_date = datetime.strptime(record_date_str, '%Y-%m-%d').date()

            # Calculate BMI.
            bmi = round(weight / ((height / 100) ** 2), 2) if height and weight and height > 0 else 0

            # Get status for each vital sign based on a separate function (assumed to exist).
            temp_status, bp_status, sugar_status, bmi_status = get_status(temp, bp_sys, bp_dia, sugar, bmi)

            # Create a new patient record with the updated data.
            new_record = Patient(
                uhid=old_record.uhid,
                version=new_version,
                is_active=True,
                # Patient Information
                name=name, age=age, gender=gender, phone_number=phone_number, email=email, address=address,
                # Vital Signs
                temperature=temp, bp_systolic=bp_sys,
                bp_diastolic=bp_dia, sugar=sugar, height=height, weight=weight, bmi=bmi,
                # Lifestyle
                smoking_status=smoking_status, alcohol_frequency=alcohol_frequency,
                physical_activity=physical_activity, diet_type=diet_type,
                # Past History
                chronic_conditions=chronic_conditions, current_medications=current_medications, allergies=allergies,
                # Status Fields
                temp_status=temp_status, bp_status=bp_status, sugar_status=sugar_status,
                bmi_status=bmi_status, record_date=record_date
            )

            # Add the new record to the session and commit.
            db.session.add(new_record)
            db.session.commit()

            # --- Audit Trail Logging (Optional but good practice) ---
            changed_to = {col.name: getattr(new_record, col.name) for col in new_record.__table__.columns if not col.name.startswith('_')}
            final_from = {k: str(v) for k, v in changed_from.items() if k in changed_to and str(changed_to[k]) != str(v)}
            final_to = {k: str(v) for k, v in changed_to.items() if k in changed_from and str(changed_from[k]) != str(v)}
            log_audit_event('PATIENT_UPDATED', f"Updated record for patient UHID {old_record.uhid}. New version: {new_version}.", final_from, final_to)
            # ----------------------------------------------------

            # Flash success message and redirect.
            flash("Patient record updated successfully! A new version has been created.", "success")
            return redirect(url_for('records'))

        except (ValueError, Exception) as e:
            # Rollback on error and flash a message.
            db.session.rollback()
            flash(f"Error updating record: {e}", "error")
            return redirect(url_for('records'))

    elif request.method == "GET":
        # Handle the GET request to display the edit form.
        # This is where the template is rendered with the patient data.
        return render_template("edit.html", patient=old_record)


import json # You might need this for other parts of your app

@app.route("/history/<string:uhid>")
@login_required
def patient_history(uhid):
    history = Patient.query.filter_by(uhid=uhid).order_by(Patient.version.desc()).all()
    
    if not history:
        flash("No history found for this patient.", "error")
        return redirect(url_for('records'))
    
    log_audit_event('VIEW_HISTORY', f"Viewed history for patient ID {uhid}.")
    
    # The line below has been REMOVED to resolve the AttributeError
    # for record in history:
    #     record.other_vitals_parsed = json.loads(record.other_vitals) if record.other_vitals else {}
    
    return render_template("patient_history.html", history=history, patient_name=history[0].name)

# --- UPLOAD PATIENT DATA ROUTE ---
@app.route("/upload_patient_data", methods=["GET", "POST"])
@login_required
def upload_patient_data():
    if request.method == "POST":
        if 'file' not in request.files:
            flash("No file part", "error")
            return redirect(request.url)
        file = request.files['file']
        if file.filename == '':
            flash("No selected file", "error")
            return redirect(request.url)
        if file and file.filename.endswith('.csv'):
            try:
                stream = StringIO(file.read().decode("UTF8"))
                csv_reader = csv.DictReader(stream)
                expected_headers = ['name', 'age', 'gender', 'phone_number', 'email', 'temperature', 'bp_systolic', 'bp_diastolic', 'sugar', 'height', 'weight', 'record_date']
                
                if not all(header in csv_reader.fieldnames for header in expected_headers):
                    missing_headers = [h for h in expected_headers if h not in csv_reader.fieldnames]
                    raise ValueError(f"Missing required CSV headers: {', '.join(missing_headers)}")

                records_added = 0
                errors = []
                for row_num, row in enumerate(csv_reader, start=2):
                    try:
                        new_uhid = generate_uhid()
                        name = row['name'].strip()
                        age = safe_convert(row.get('age', ''), int, "Age")
                        gender = row['gender'].strip()
                        phone_number = row.get('phone_number', '').strip() or None
                        email = row.get('email', '').strip() or None
                        temp = safe_convert(row.get('temperature', ''), float, "Temperature")
                        bp_sys = safe_convert(row.get('bp_systolic', ''), int, "Systolic BP")
                        bp_dia = safe_convert(row.get('bp_diastolic', ''), int, "Diastolic BP")
                        sugar = safe_convert(row.get('sugar', ''), int, "Blood Sugar")
                        height = safe_convert(row.get('height', ''), float, "Height")
                        weight = safe_convert(row.get('weight', ''), float, "Weight")
                        record_date_str = row['record_date'].strip()
                        other_vitals_str = row.get('other_vitals', '').strip() or None

                        if not name: raise ValueError("Name is required.")
                        if not gender: raise ValueError("Gender is required.")
                        try:
                            record_date = datetime.strptime(record_date_str, '%Y-%m-%d').date()
                        except ValueError:
                            raise ValueError("Record Date must be in YYYY-MM-DD format.")

                        bmi = round(weight / ((height / 100) ** 2), 2) if height and weight and height > 0 else 0
                        temp_status, bp_status, sugar_status, bmi_status = get_status(temp, bp_sys, bp_dia, sugar, bmi)
                        
                        if other_vitals_str:
                            try:
                                json.loads(other_vitals_str)
                            except json.JSONDecodeError:
                                raise ValueError("Other vitals must be a valid JSON string.")

                        new_patient = Patient(
                            uhid=new_uhid, name=name, age=age, gender=gender, phone_number=phone_number, email=email,
                            temperature=temp, bp_systolic=bp_sys, bp_diastolic=bp_dia, sugar=sugar, height=height, weight=weight, bmi=bmi,
                            temp_status=temp_status, bp_status=bp_status, sugar_status=sugar_status, bmi_status=bmi_status,
                            record_date=record_date, version=1, is_active=True, other_vitals=other_vitals_str
                        )
                        db.session.add(new_patient)
                        records_added += 1
                    except ValueError as ve:
                        errors.append(f"Row {row_num}: {ve}")
                    except Exception as ex:
                        errors.append(f"Row {row_num}: Unexpected error - {ex}")

                db.session.commit()
                if records_added > 0:
                    log_audit_event('DATA_UPLOADED', f"Successfully uploaded {records_added} patient records from CSV.")
                    flash(f"Successfully uploaded {records_added} patient records!", "success")
                if errors:
                    flash(f"Completed with {len(errors)} errors. See details on the upload page.", "warning")
                    session['upload_errors'] = errors
                    return redirect(url_for('upload_patient_data'))
                return redirect(url_for('records'))
            except Exception as e:
                db.session.rollback()
                flash(f"Error processing CSV file: {e}", "error")
                log_audit_event('DATA_UPLOAD_FAILED', f"Failed to upload patient data: {e}")
        else:
            flash("Invalid file type. Please upload a CSV file.", "error")
            log_audit_event('DATA_UPLOAD_FAILED', "Attempted to upload invalid file type.")
        return redirect(url_for('upload_patient_data'))
    
    upload_errors = session.pop('upload_errors', [])
    return render_template("upload.html", upload_errors=upload_errors)

# --- ADMIN & USER MANAGEMENT ROUTES ---
@app.route("/create_user", methods=["GET", "POST"])
@admin_required
def create_user():
    """
    Handles user creation for administrators.
    - GET: Renders the create_user form.
    - POST: Processes the form data to create a new user.
    """
    if request.method == "POST":
        new_username = request.form["new_username"].strip()
        new_password = request.form["new_password"].strip()
        confirm_password = request.form["confirm_password"].strip()
        user_role = request.form["user_role"].strip()
        user_department = request.form["user_department"].strip()

        # --- Basic Server-Side Validation ---
        if not new_username or not new_password or not confirm_password or not user_role or not user_department:
            flash("All fields are required.", "error")
            return redirect(url_for("create_user"))

        existing_user = User.query.filter_by(username=new_username).first()
        if existing_user:
            flash("Username already exists. Please choose a different one.", "error")
            return redirect(url_for("create_user"))

        if new_password != confirm_password:
            flash("Passwords do not match.", "error")
            return redirect(url_for("create_user"))

        if len(new_password) < 8 or \
           not any(char.isdigit() for char in new_password) or \
           not any(char.isupper() for char in new_password) or \
           not any(char.islower() for char in new_password):
            flash("Password must be at least 8 characters long and contain at least one uppercase letter, one lowercase letter, and one digit.", "error")
            return redirect(url_for("create_user"))
        
        try:
            hashed_password = generate_password_hash(new_password)
            new_user = User(username=new_username, password_hash=hashed_password, role=user_role, department=user_department)
            db.session.add(new_user)
            db.session.commit()
            log_audit_event('USER_CREATED', f"Admin created new user '{new_username}' with role '{user_role}' and department '{user_department}'.")
            flash("User created successfully!", "success")
            return redirect(url_for("users_list"))
        except Exception as e:
            db.session.rollback()
            flash(f"An error occurred: {e}", "error")
            log_audit_event('USER_CREATION_FAILED', f"Failed to create user '{new_username}': {e}")
            return redirect(url_for("create_user"))
    else:
        users = User.query.all()
        print(f"Fetched users: {users}") # <-- Add this line
        return render_template("create_user.html", users=users)
        return render_template("create_user.html")




@app.route('/delete_user/<int:user_id>', methods=['POST'])
def delete_user(user_id):
    user_to_delete = User.query.get_or_404(user_id)
    try:
        db.session.delete(user_to_delete)
        db.session.commit()
        flash('User deleted successfully!', 'success')
        return redirect(url_for('create_user'))
    except Exception as e:
        db.session.rollback()
        flash(f'Error deleting user: {e}', 'error')
        return redirect(url_for('create_user'))


# --- OVERVIEW ROUTE ---
@app.route("/overview")
@login_required
def overview():
    patients_data = Patient.query.filter_by(is_active=True).all()
    total_patients = len(patients_data)
    avg_age = 0
    male_percentage = 0
    female_percentage = 0
    other_percentage = 0
    health_status_chart_data = {'labels': [], 'data': [], 'backgroundColors': []}
    gender_chart_data = {'labels': [], 'data': [], 'backgroundColors': []}
    monthly_trends_chart_data = {'labels': [], 'data': [], 'borderColor': '', 'backgroundColor': ''}
    bmi_status_chart_data = {'labels': [], 'data': [], 'backgroundColors': []}
    age_group_chart_data = {'labels': [], 'data': [], 'backgroundColors': []}
    abnormal_vitals_breakdown_chart_data = {'labels': [], 'data': [], 'backgroundColors': []}

    if total_patients > 0:
        valid_age_patients = [p for p in patients_data if p.age is not None]
        total_age = sum(p.age for p in valid_age_patients)
        avg_age = round(total_age / len(valid_age_patients)) if valid_age_patients else 0

        male_count = sum(1 for p in patients_data if p.gender and p.gender.lower() == 'male')
        female_count = sum(1 for p in patients_data if p.gender and p.gender.lower() == 'female')
        other_gender_count = total_patients - male_count - female_count
        male_percentage = round((male_count / total_patients) * 100)
        female_percentage = round((female_count / total_patients) * 100)
        other_percentage = 100 - male_percentage - female_percentage

        normal_vitals_count = sum((1 if p.temp_status == 'Normal' else 0) + (1 if p.bp_status == 'Normal' else 0) + (1 if p.sugar_status == 'Normal' else 0) + (1 if p.bmi_status == 'Normal' else 0) for p in patients_data)
        abnormal_vitals_count = (total_patients * 4) - normal_vitals_count
        health_status_chart_data = {'labels': ['Normal', 'Abnormal'], 'data': [normal_vitals_count, abnormal_vitals_count], 'backgroundColors': ['#4CAF50', '#F44336']}
        gender_chart_data = {'labels': ['Male', 'Female', 'Other'], 'data': [male_count, female_count, other_gender_count], 'backgroundColors': ['#2196F3', '#E91E63', '#9E9E9E']}

        monthly_counts = Counter(p.record_date.strftime('%Y-%m') for p in patients_data if p.record_date)
        sorted_months = sorted(monthly_counts.keys())
        monthly_trends_chart_data = {'labels': [datetime.strptime(ym, '%Y-%m').strftime('%b %Y') for ym in sorted_months], 'data': [monthly_counts[ym] for ym in sorted_months], 'borderColor': '#007bff', 'backgroundColor': 'rgba(0, 123, 255, 0.1)'}

        bmi_normal_count = sum(1 for p in patients_data if p.bmi_status == 'Normal')
        bmi_abnormal_count = total_patients - bmi_normal_count
        bmi_status_chart_data = {'labels': ['Normal BMI', 'Abnormal BMI'], 'data': [bmi_normal_count, bmi_abnormal_count], 'backgroundColors': ['#8BC34A', '#FF9800']}

        age_groups = {'0-18': 0, '19-35': 0, '36-55': 0, '56-75': 0, '76+': 0}
        for p in valid_age_patients:
            if p.age <= 18: age_groups['0-18'] += 1
            elif 19 <= p.age <= 35: age_groups['19-35'] += 1
            elif 36 <= p.age <= 55: age_groups['36-55'] += 1
            elif 56 <= p.age <= 75: age_groups['56-75'] += 1
            else: age_groups['76+'] += 1
        age_group_chart_data = {'labels': list(age_groups.keys()), 'data': list(age_groups.values()), 'backgroundColor': ['#4CAF50', '#2196F3', '#FFC107', '#E91E63', '#9C27B0'], 'borderColor': '#ddd', 'borderWidth': 1}

        abnormal_temp_count = sum(1 for p in patients_data if p.temp_status == 'Abnormal')
        abnormal_bp_count = sum(1 for p in patients_data if p.bp_status == 'Abnormal')
        abnormal_sugar_count = sum(1 for p in patients_data if p.sugar_status == 'Abnormal')
        abnormal_bmi_count = sum(1 for p in patients_data if p.bmi_status == 'Abnormal')
        abnormal_vitals_breakdown_chart_data = {'labels': ['Temperature', 'Blood Pressure', 'Blood Sugar', 'BMI'], 'data': [abnormal_temp_count, abnormal_bp_count, abnormal_sugar_count, abnormal_bmi_count], 'backgroundColor': ['#F44336', '#FF5722', '#FFC107', '#795548'], 'borderColor': '#ddd', 'borderWidth': 1}

    log_audit_event('VIEW_OVERVIEW', 'User accessed the overview dashboard.')
    return render_template("overview.html", total_patients=total_patients, avg_age=avg_age, male_percentage=male_percentage, female_percentage=female_percentage, other_percentage=other_percentage, health_status_chart_data=health_status_chart_data, gender_chart_data=gender_chart_data, monthly_trends_chart_data=monthly_trends_chart_data, bmi_status_chart_data=bmi_status_chart_data, age_group_chart_data=age_group_chart_data, abnormal_vitals_breakdown_chart_data=abnormal_vitals_breakdown_chart_data)


# --- AUDIT LOG ROUTES ---
@app.route("/audit_logs")
@admin_required
def view_audit_logs():
    page = request.args.get('page', 1, type=int)
    per_page = 10
    query = AuditLog.query
    filter_username = request.args.get('username')
    filter_event_type = request.args.get('event_type')
    filter_start_date = request.args.get('start_date')
    filter_end_date = request.args.get('end_date')

    if filter_username: query = query.filter(AuditLog.username.ilike(f"%{filter_username}%"))
    if filter_event_type: query = query.filter(AuditLog.event_type == filter_event_type)
    if filter_start_date: query = query.filter(AuditLog.timestamp >= datetime.strptime(filter_start_date, '%Y-%m-%d'))
    if filter_end_date:
        end_date_obj = datetime.strptime(filter_end_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
        query = query.filter(AuditLog.timestamp <= end_date_obj)

    all_logs = query.order_by(AuditLog.timestamp.asc()).all()
    sessions = OrderedDict()
    for log in all_logs:
        if log.session_id not in sessions:
            sessions[log.session_id] = {'session_id': log.session_id, 'username': log.username, 'ip_address': log.ip_address, 'start_time': log.timestamp, 'actions': []}
        sessions[log.session_id]['actions'].append(log)

    sorted_sessions = sorted(sessions.values(), key=lambda s: s['start_time'], reverse=True)
    start = (page - 1) * per_page
    end = start + per_page
    paginated_sessions = sorted_sessions[start:end]
    pagination = CustomPagination(paginated_sessions, page, per_page, len(sorted_sessions))
    distinct_users = [u.username for u in db.session.query(AuditLog.username).distinct().order_by(AuditLog.username)]
    distinct_events = [e.event_type for e in db.session.query(AuditLog.event_type).distinct().order_by(AuditLog.event_type)]

    return render_template("audit_logs.html", logs=pagination, distinct_users=distinct_users, distinct_events=distinct_events, filters=request.args)

IST = pytz.timezone('Asia/Kolkata')
UTC = pytz.timezone('UTC')

# 2. Define the filter functions
def to_ist_datetime(stored_dt):
    """
    Assumes the stored datetime is ALREADY IST and just needs formatting.
    """
    if not stored_dt: return ""
    # Localize tells pytz that this datetime's timezone is IST
    ist_dt = IST.localize(stored_dt) 
    return ist_dt.strftime('%d %b %Y, %I:%M:%S %p')

def to_ist_time(stored_dt):
    """
    Assumes the stored datetime is ALREADY IST and just needs formatting.
    """
    if not stored_dt: return ""
    ist_dt = IST.localize(stored_dt)
    return ist_dt.strftime('%I:%M:%S %p')

# Register the filters
app.jinja_env.filters['to_ist_datetime'] = to_ist_datetime
app.jinja_env.filters['to_ist_time'] = to_ist_time

@app.route("/audit_logs/export")
@admin_required
def export_logs():
    query = AuditLog.query
    # --- Your existing filter logic is correct, so it's kept as is ---
    filter_username = request.args.get('username')
    filter_event_type = request.args.get('event_type')
    filter_start_date = request.args.get('start_date')
    filter_end_date = request.args.get('end_date')

    if filter_username: query = query.filter(AuditLog.username.ilike(f"%{filter_username}%"))
    if filter_event_type: query = query.filter_by(event_type=filter_event_type)
    if filter_start_date: query = query.filter(AuditLog.timestamp >= datetime.strptime(filter_start_date, '%Y-%m-%d'))
    if filter_end_date:
        end_date_obj = datetime.strptime(filter_end_date, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
        query = query.filter(AuditLog.timestamp <= end_date_obj)

    logs_to_export = query.order_by(AuditLog.timestamp.desc()).all()
    output = StringIO()
    writer = csv.writer(output)
    writer.writerow(['Timestamp (IST)', 'Username', 'IP Address', 'Event Type', 'Details', 'Changed From', 'Changed To'])
    
    for log in logs_to_export:
        # ** FIX IS HERE: Convert timestamp to IST before writing **
        utc_dt = log.timestamp
        # If the datetime from DB is naive, make it aware that it's UTC
        if utc_dt.tzinfo is None:
            utc_dt = UTC.localize(utc_dt)
        
        # Convert to IST
        ist_dt = utc_dt.astimezone(IST)
        
        # Format the converted IST time
        formatted_time = ist_dt.strftime("%d-%m-%Y %I:%M:%S %p")
        
        writer.writerow([formatted_time, log.username, log.ip_address, log.event_type, log.event_details, log.changed_from, log.changed_to])
    
    response = Response(output.getvalue(), mimetype='text/csv')
    response.headers.set("Content-Disposition", "attachment", filename="audit_logs_export.csv")
    log_audit_event('LOG_EXPORT', f"User exported {len(logs_to_export)} log entries.")
    return response

# --- MEDICATION REMINDER ROUTES ---
@app.route("/reminders")
@login_required
def view_reminders():
    now = datetime.utcnow()
    due_reminders = Reminder.query.filter(Reminder.status == 'Scheduled', Reminder.reminder_time <= now).all()
    for reminder in due_reminders:
        reminder.status = 'Sent'
    db.session.commit()
    
    filter_type = request.args.get('reminder_type', '')
    query = Prescription.query
    if filter_type:
        query = query.filter(Prescription.reminder_type == filter_type)
        
    prescriptions = query.order_by(Prescription.created_at.desc()).all()
    return render_template("view_reminders.html", prescriptions=prescriptions, current_filter=filter_type)

@app.route("/set_reminder", methods=["GET", "POST"])
@login_required
def set_reminder():
    if request.method == "POST":
        try:
            uhid = request.form.get('uhid')
            reminder_type = request.form.get('reminder_type')

            patient = db.session.get(Patient, int(uhid))
            if not patient: raise ValueError("Selected patient not found.")

            if reminder_type == 'Medication':
                doctor_name = request.form.get('doctor_name').strip()
                medication = request.form.get('medication_name').strip()
                frequency = int(request.form.get('frequency'))
                duration = int(request.form.get('duration'))
                start_date_str = request.form.get('start_date')
                special_note = request.form.get('special_note', '').strip()
                med_hours = request.form.getlist('med_time_hr')
                med_minutes = request.form.getlist('med_time_min')
                med_ampms = request.form.getlist('med_time_ampm')

                if not all([doctor_name, medication, frequency, duration, start_date_str]) or len(med_hours) != frequency:
                    raise ValueError("Please fill out all required fields for medication reminder.")

                start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
                
                new_prescription = Prescription(
                    uhid=patient.id, reminder_type='Medication',
                    doctor_name=doctor_name, medication_name=medication,
                    frequency=frequency, duration=duration,
                    special_note=special_note, start_date=start_date
                )
                db.session.add(new_prescription)
                db.session.flush()
                
                for day in range(duration):
                    current_date = start_date + timedelta(days=day)
                    for i in range(frequency):
                        hour_12, minute, ampm = int(med_hours[i]), int(med_minutes[i]), med_ampms[i]
                        hour_24 = hour_12
                        if ampm == 'PM' and hour_12 != 12: hour_24 += 12
                        if ampm == 'AM' and hour_12 == 12: hour_24 = 0
                        med_time = time(hour_24, minute)
                        reminder_datetime = datetime.combine(current_date, med_time)
                        
                        instance_reminder = Reminder(prescription_id=new_prescription.id, reminder_time=reminder_datetime)
                        db.session.add(instance_reminder)
                
                log_audit_event('REMINDER_SET', f"Scheduled '{medication}' for {patient.name}.")

            elif reminder_type == 'Follow-up':
                follow_up_date_str = request.form.get('follow_up_date')
                special_note = request.form.get('special_note', '').strip()
                
                hour_12 = int(request.form.get('follow_up_hr'))
                minute = int(request.form.get('follow_up_min'))
                ampm = request.form.get('follow_up_ampm')

                if not follow_up_date_str:
                    raise ValueError("Please set a date for the follow-up.")
                
                follow_up_date = datetime.strptime(follow_up_date_str, '%Y-%m-%d').date()
                hour_24 = hour_12
                if ampm == 'PM' and hour_12 != 12: hour_24 += 12
                if ampm == 'AM' and hour_12 == 12: hour_24 = 0
                follow_up_time = time(hour_24, minute)
                follow_up_datetime = datetime.combine(follow_up_date, follow_up_time)

                new_prescription = Prescription(
                    uhid=patient.id, reminder_type='Follow-up',
                    medication_name="Follow-up Appointment",
                    special_note=special_note, follow_up_datetime=follow_up_datetime
                )
                db.session.add(new_prescription)
                db.session.flush()

                instance_reminder = Reminder(prescription_id=new_prescription.id, reminder_time=follow_up_datetime)
                db.session.add(instance_reminder)
                
                log_audit_event('REMINDER_SET', f"Scheduled a follow-up for {patient.name}.")

            elif reminder_type == 'Other':
                title = request.form.get('other_title').strip()
                special_note = request.form.get('special_note', '').strip()

                if not title:
                    raise ValueError("Please provide a title for the 'Other' reminder.")

                new_prescription = Prescription(
                    uhid=patient.id,
                    reminder_type='Other',
                    medication_name=title,
                    special_note=special_note
                )
                db.session.add(new_prescription)
                log_audit_event('REMINDER_SET', f"Created an 'Other' reminder titled '{title}' for {patient.name}.")

            db.session.commit()
            flash(f"{reminder_type} reminder for {patient.name} has been scheduled!", "success")
            return redirect(url_for('view_reminders'))

        except Exception as e:
            db.session.rollback()
            flash(f"Error setting reminder: {e}", "error")

    patients = Patient.query.filter(Patient.is_active==True).order_by(Patient.name).all()
    preselected_uhid = request.args.get('uhid', type=int)
    return render_template("set_reminder.html", patients=patients, preselected_uhid=preselected_uhid)

# --- INITIALIZATION ---
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        if not User.query.filter_by(username='admin').first():
            hashed_password = generate_password_hash("pass123")
            admin_user = User(username='admin', password_hash=hashed_password, role='admin')
            db.session.add(admin_user)
            db.session.commit()
            print("Default 'admin' user created with password 'pass123'.")
        if not User.query.filter_by(username='user1').first():
            hashed_password = generate_password_hash("userpass")
            health_worker_user = User(username='user1', password_hash=hashed_password, role='health_worker')
            db.session.add(health_worker_user)
            db.session.commit()
            print("Default 'user1' (health_worker role) created with password 'userpass'.")
    app.run(debug=True)
