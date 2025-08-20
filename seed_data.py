import random
from datetime import datetime, timedelta
from main import Patient, db, app, generate_patient_id # Import the new ID generator

# --- DATA FOR GENERATION ---
first_names = [
    "Aarav", "Vivaan", "Aditya", "Vihaan", "Arjun", "Sai", "Reyansh", "Ayaan", "Krishna", "Ishaan",
    "Saanvi", "Aadya", "Kiara", "Diya", "Pari", "Ananya", "Riya", "Aarohi", "Amaira", "Myra"
]
last_names = [
    "Sharma", "Verma", "Gupta", "Singh", "Kumar", "Patel", "Shah", "Reddy", "Joshi", "Mehta"
]

def get_random_vitals():
    """Generates a set of random but plausible vital signs."""
    temp = round(random.uniform(97.0, 102.5), 1)
    bp_sys = random.randint(85, 150)
    bp_dia = random.randint(55, 95)
    sugar = random.randint(70, 180)
    return temp, bp_sys, bp_dia, sugar

def get_status(temp, bp_sys, bp_dia, sugar, bmi):
    """Calculates the status for each vital sign."""
    temp_status = "Normal" if 97.0 <= temp <= 99.0 else "Abnormal"
    bp_status = "Normal" if 90 <= bp_sys <= 120 and 60 <= bp_dia <= 80 else "Abnormal"
    sugar_status = "Normal" if 80 <= sugar <= 110 else "Abnormal"
    bmi_status = "Normal" if 18.5 <= bmi <= 24.9 else "Abnormal"
    return temp_status, bp_status, sugar_status, bmi_status

def create_seed_data():
    """Generates and inserts 300 patient records into the database."""
    with app.app_context():
        print("Starting to generate 300 patient records...")

        for i in range(300):
            # --- Create Patient Data ---
            name = f"{random.choice(first_names)} {random.choice(last_names)}"
            age = random.randint(18, 85)
            gender = random.choice(["Male", "Female", "Other"])
            phone_number = f"9{random.randint(100000000, 999999999)}"
            email = f"{name.lower().replace(' ', '.')}{i}@example.com"
            height = round(random.uniform(150.0, 190.0), 1)
            weight = round(random.uniform(50.0, 110.0), 1)
            
            temp, bp_sys, bp_dia, sugar = get_random_vitals()
            
            bmi = round(weight / ((height / 100) ** 2), 2)
            
            temp_status, bp_status, sugar_status, bmi_status = get_status(temp, bp_sys, bp_dia, sugar, bmi)
            
            record_date = (datetime.now() - timedelta(days=random.randint(0, 365))).strftime('%Y-%m-%d')

            # --- Create Patient Object with new ID ---
            new_patient = Patient(
                patient_id=generate_patient_id(), # Use the new ID generator
                name=name,
                age=age,
                gender=gender,
                phone_number=phone_number,
                email=email,
                temperature=temp,
                bp_systolic=bp_sys,
                bp_diastolic=bp_dia,
                sugar=sugar,
                height=height,
                weight=weight,
                bmi=bmi,
                temp_status=temp_status,
                bp_status=bp_status,
                sugar_status=sugar_status,
                bmi_status=bmi_status,
                record_date=record_date
            )
            
            db.session.add(new_patient)

            if (i + 1) % 25 == 0:
                print(f"  ... {i + 1} records prepared.")

        try:
            db.session.commit()
            print("\nSuccessfully committed 300 new patient records to the database!")
        except Exception as e:
            db.session.rollback()
            print(f"\nAn error occurred: {e}")
            print("Rolling back changes. No data was added.")
        finally:
            print("Database session closed.")


if __name__ == "__main__":
    create_seed_data()
