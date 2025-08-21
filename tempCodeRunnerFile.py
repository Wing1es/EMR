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
            name = request.form["name"].strip()
            age = safe_convert(request.form.get("age", ""), int, "Age")
            gender = request.form["gender"].strip()
            phone_number = request.form.get('phone_number', '').strip()
            email = request.form.get('email', '').strip()
            temp = safe_convert(request.form.get("temp", ""), float, "Temperature")
            bp_sys = safe_convert(request.form.get("bp_sys", ""), int, "Systolic BP")
            bp_dia = safe_convert(request.form.get("bp_dia", ""), int, "Diastolic BP")
            sugar = safe_convert(request.form.get("sugar", ""), int, "Blood Sugar")
            height = safe_convert(request.form.get("height", ""), float, "Height")
            weight = safe_convert(request.form.get("weight", ""), float, "Weight")
            
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
                name=name, age=age, gender=gender, phone_number=phone_number, email=email,
                temperature=temp, bp_systolic=bp_sys,
                bp_diastolic=bp_dia, sugar=sugar, height=height, weight=weight, bmi=bmi,
                temp_status=temp_status, bp_status=bp_status, sugar_status=sugar_status,
                bmi_status=bmi_status, record_date=record_date,
                other_vitals=json.dumps({})  # Set other_vitals to an empty JSON object
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
        other_vitals_data = json.loads(old_record.other_vitals) if old_record.other_vitals else {}
        return render_template("edit.html", patient=old_record, other_vitals_data=other_vitals_data)
