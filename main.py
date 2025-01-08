import asyncio
import threading
import tkinter as tk
from tkinter import messagebox
from bleak import BleakClient
import sqlite3
import time

# Service and characteristic UUIDs
SERVICE_UUID = "0000fff0-0000-1000-8000-00805f9b34fb"
NOTIFY_CHARACTERISTIC_UUID = "0000fff1-0000-1000-8000-00805f9b34fb"  # Notify
WRITE_CHARACTERISTIC_UUID = "0000fff2-0000-1000-8000-00805f9b34fb"  # Write

DB_NAME = "metrics.db"

latest_metrics = {
    "Weight (kg)": None,
    "BMI": None,
    "BodyFat%": None,
    "Fat Mass (kg)": None,
    "Fat-Free Mass (kg)": None,
    "Lean Body Mass (kg)": None,
    "Total Body Water (L)": None,
    "Body Hydration%": None,
    "Muscle Mass (kg, est.)": None,
    "Bone Mass% (est.)": None,
    "Metabolic Age (est.)": None,
    "Protein% (est.)": None,
    "Skeletal Muscle% (est.)": None,
    "Subcutaneous Fat% (est.)": None,
    "Visceral Fat (est.)": None,
    "Raw Impedance": None
}

def init_db():
    """Initialize the database and create tables if they do not exist."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()

    # Users table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            age INTEGER,
            height REAL,
            gender TEXT
        )
    """)

    # Measurements table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS measurements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            timestamp INTEGER,
            weight REAL,
            bmi REAL,
            body_fat REAL,
            fat_mass REAL,
            fat_free_mass REAL,
            lean_body_mass REAL,
            total_body_water REAL,
            body_hydration REAL,
            muscle_mass REAL,
            bone_mass_percent REAL,
            metabolic_age REAL,
            protein_percent REAL,
            skeletal_muscle_percent REAL,
            subcutaneous_fat_percent REAL,
            visceral_fat REAL,
            raw_impedance REAL,
            FOREIGN KEY(user_id) REFERENCES users(id)
        )
    """)

    conn.commit()
    conn.close()

def load_users():
    """Load all users from the database and return as a list of (id, name) tuples."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT id, name FROM users")
    rows = cursor.fetchall()
    conn.close()
    return rows

def create_user(name, age, height, gender):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT INTO users (name, age, height, gender) VALUES (?, ?, ?, ?)",
                   (name, age, height, gender))
    conn.commit()
    conn.close()

def get_user_data(user_id):
    """Fetch full user record (age, height, gender) by user_id."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT age, height, gender FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return row  # (age, height, gender) or None

def decode_metric(data, offset, scale=1):
    if len(data) > offset + 1:
        raw_value = (data[offset] << 8) | data[offset + 1]
        return raw_value / scale
    else:
        return None

def calculate_bmr(weight_kg, height_m, age, is_male):
    height_cm = height_m * 100
    if is_male:
        bmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age) + 5
    else:
        bmr = (10 * weight_kg) + (6.25 * height_cm) - (5 * age) - 161
    return bmr

def estimate_metabolic_age_v2(bmr, is_male):
    if is_male:
        reference = {20: 1850, 30: 1750, 40: 1650, 50: 1550, 60: 1450}
    else:
        reference = {20: 1750, 30: 1650, 40: 1550, 50: 1450, 60: 1350}

    if bmr >= reference[20]:
        return 20
    if bmr <= reference[60]:
        return 60

    sorted_ages = sorted(reference.keys())
    for i in range(len(sorted_ages)-1):
        age_low = sorted_ages[i]
        age_high = sorted_ages[i+1]
        bmr_low = reference[age_low]
        bmr_high = reference[age_high]

        if bmr <= bmr_low and bmr >= bmr_high:
            ratio = (bmr_low - bmr) / (bmr_low - bmr_high)
            metabolic_age = age_low + (age_high - age_low)*ratio
            return metabolic_age
    return 60

def calculate_metrics(weight_kg, impedance, age, height_m, is_male):
    bmi = weight_kg / (height_m ** 2)

    if is_male:
        body_fat = (bmi * 1.2) + (age * 0.23) - 16.2
    else:
        body_fat = (bmi * 1.2) + (age * 0.23) - 5.4

    fat_mass = (body_fat / 100.0) * weight_kg
    ffm = weight_kg - fat_mass

    # Boer formula LBM
    if is_male:
        lbm = (0.4071 * weight_kg) + (0.267 * height_m) - 19.2
    else:
        lbm = (0.252 * weight_kg) + (0.473 * height_m) - 48.3

    # Hume & Weyers TBW
    if is_male:
        tbw = (0.194786 * height_m) + (0.296785 * weight_kg) - 14.012934
    else:
        tbw = (0.34454 * height_m) + (0.183809 * weight_kg) - 35.270121

    hydration = (tbw / weight_kg) * 100

    muscle_mass_est = ffm * 0.50
    bone_mass_kg = 0.04 * lbm
    bone_mass_percent_est = (bone_mass_kg / weight_kg) * 100

    bmr = calculate_bmr(weight_kg, height_m, age, is_male)
    metabolic_age_est = estimate_metabolic_age_v2(bmr, is_male)

    protein_mass_kg = 0.20 * lbm
    protein_percent_est = (protein_mass_kg / weight_kg) * 100

    skeletal_muscle_percent_est = (muscle_mass_est / weight_kg) * 100
    subcutaneous_fat_percent_est = body_fat * 0.8
    visceral_fat_est = body_fat * 0.2

    metrics = {
        "Weight (kg)": weight_kg,
        "BMI": bmi,
        "BodyFat%": body_fat,
        "Fat Mass (kg)": fat_mass,
        "Fat-Free Mass (kg)": ffm,
        "Lean Body Mass (kg)": lbm,
        "Total Body Water (L)": tbw,
        "Body Hydration%": hydration,
        "Muscle Mass (kg, est.)": muscle_mass_est,
        "Bone Mass% (est.)": bone_mass_percent_est,
        "Metabolic Age (est.)": metabolic_age_est,
        "Protein% (est.)": protein_percent_est,
        "Skeletal Muscle% (est.)": skeletal_muscle_percent_est,
        "Subcutaneous Fat% (est.)": subcutaneous_fat_percent_est,
        "Visceral Fat (est.)": visceral_fat_est
    }
    return metrics

def decode_data(data):
    try:
        data_type = data[0]
        if data_type == 0x10:
            weight = decode_metric(data, 3, scale=100)
            impedance = decode_metric(data, 5, scale=1)

            if weight is not None and impedance is not None and impedance > 0:
                # Check selected user
                selected_user_val = selected_user.get()
                if selected_user_val == "Select User":
                    print("No user selected.")
                    return None

                user_id = int(selected_user_val.split(":")[0])
                user_data = get_user_data(user_id)
                if user_data is None:
                    print("User not found in DB.")
                    return None

                user_age_val, user_height_val, user_gender_val = user_data
                is_male = (user_gender_val.lower() == "male")

                metrics = calculate_metrics(weight, impedance, user_age_val, user_height_val, is_male)
                metrics["Raw Impedance"] = impedance
                return metrics
    except Exception as e:
        print(f"Error decoding data: {e}")
    return None

async def notification_handler(sender, data):
    print(f"Notification from {sender}: {data}")
    metrics = decode_data(data)
    if metrics:
        for k, v in metrics.items():
            latest_metrics[k] = v
        if ui_root:
            ui_root.after(0, update_ui)

async def configure_scale(client):
    config_data = bytearray([0x13, 0x01, 0x10, 0x00, 0x00])
    await client.write_gatt_char(WRITE_CHARACTERISTIC_UUID, config_data)
    print("Configuration sent to scale.")

async def connect_to_scale(address):
    async with BleakClient(address) as client:
        print("Connected to scale.")
        await client.start_notify(NOTIFY_CHARACTERISTIC_UUID, notification_handler)
        print("Subscribed to notifications.")

        await configure_scale(client)
        await asyncio.sleep(30)  # Wait for notifications
        await client.stop_notify(NOTIFY_CHARACTERISTIC_UUID)
        print("Disconnected from scale.")

def start_ble_loop(address):
    asyncio.run(connect_to_scale(address))

def update_ui():
    for key, label in metric_labels.items():
        value = latest_metrics[key]
        if value is not None:
            if isinstance(value, float):
                if '%' in key:
                    label.config(text=f"{key}: {value:.2f}%")
                elif 'kg' in key:
                    label.config(text=f"{key}: {value:.2f} kg")
                elif 'L' in key:
                    label.config(text=f"{key}: {value:.2f} L")
                else:
                    label.config(text=f"{key}: {value:.2f}")
            else:
                label.config(text=f"{key}: {value}")

def save_data():
    selected_user_val = selected_user.get()
    if selected_user_val == "Select User":
        messagebox.showwarning("Warning", "Please select a user before saving.")
        return

    if latest_metrics["Weight (kg)"] is None:
        messagebox.showwarning("Warning", "No measurement data available to save.")
        return

    user_id = int(selected_user_val.split(":")[0])

    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("""
        INSERT INTO measurements (
            user_id, timestamp, weight, bmi, body_fat, fat_mass, fat_free_mass,
            lean_body_mass, total_body_water, body_hydration, muscle_mass,
            bone_mass_percent, metabolic_age, protein_percent, skeletal_muscle_percent,
            subcutaneous_fat_percent, visceral_fat, raw_impedance
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        user_id,
        int(time.time()),
        latest_metrics["Weight (kg)"],
        latest_metrics["BMI"],
        latest_metrics["BodyFat%"],
        latest_metrics["Fat Mass (kg)"],
        latest_metrics["Fat-Free Mass (kg)"],
        latest_metrics["Lean Body Mass (kg)"],
        latest_metrics["Total Body Water (L)"],
        latest_metrics["Body Hydration%"],
        latest_metrics["Muscle Mass (kg, est.)"],
        latest_metrics["Bone Mass% (est.)"],
        latest_metrics["Metabolic Age (est.)"],
        latest_metrics["Protein% (est.)"],
        latest_metrics["Skeletal Muscle% (est.)"],
        latest_metrics["Subcutaneous Fat% (est.)"],
        latest_metrics["Visceral Fat (est.)"],
        latest_metrics["Raw Impedance"]
    ))
    conn.commit()
    conn.close()

    messagebox.showinfo("Success", "Data saved successfully.")

def create_profile():
    name = name_entry.get().strip()
    age_str = age_entry.get().strip()
    height_str = height_entry.get().strip()
    gender = gender_entry.get().strip().lower()

    if not name or not age_str or not height_str or not gender:
        messagebox.showwarning("Warning", "Please fill all profile fields.")
        return

    try:
        age_val = int(age_str)
        height_val = float(height_str)
    except ValueError:
        messagebox.showwarning("Warning", "Invalid age or height.")
        return

    if gender not in ["male", "female"]:
        messagebox.showwarning("Warning", "Gender must be 'male' or 'female'.")
        return

    create_user(name, age_val, height_val, gender)
    messagebox.showinfo("Success", "User profile created successfully.")
    update_user_list()

def update_user_list():
    users = load_users()
    menu = user_dropdown["menu"]
    menu.delete(0, "end")
    user_ids_names = ["Select User"]
    for uid, uname in users:
        user_ids_names.append(f"{uid}: {uname}")
    selected_user.set("Select User")
    for val in user_ids_names:
        menu.add_command(label=val, command=lambda v=val: selected_user.set(v))

####################
# TKINTER UI SETUP #
####################

ui_root = tk.Tk()
ui_root.title("Scale Metrics with User Profiles & DB")

# Profile creation frame
profile_frame = tk.LabelFrame(ui_root, text="Create New Profile")
profile_frame.grid(row=0, column=0, padx=10, pady=10, sticky="w")

tk.Label(profile_frame, text="Name:").grid(row=0, column=0, sticky="e")
name_entry = tk.Entry(profile_frame)
name_entry.grid(row=0, column=1, padx=5, pady=5)

tk.Label(profile_frame, text="Age:").grid(row=1, column=0, sticky="e")
age_entry = tk.Entry(profile_frame)
age_entry.grid(row=1, column=1, padx=5, pady=5)

tk.Label(profile_frame, text="Height (m):").grid(row=2, column=0, sticky="e")
height_entry = tk.Entry(profile_frame)
height_entry.grid(row=2, column=1, padx=5, pady=5)

tk.Label(profile_frame, text="Gender (male/female):").grid(row=3, column=0, sticky="e")
gender_entry = tk.Entry(profile_frame)
gender_entry.grid(row=3, column=1, padx=5, pady=5)

create_user_button = tk.Button(profile_frame, text="Create Profile", command=create_profile)
create_user_button.grid(row=4, column=0, columnspan=2, pady=10)

# User selection frame
user_sel_frame = tk.LabelFrame(ui_root, text="Select User Profile")
user_sel_frame.grid(row=1, column=0, padx=10, pady=10, sticky="w")

selected_user = tk.StringVar(value="Select User")
user_dropdown = tk.OptionMenu(user_sel_frame, selected_user, "Select User")
user_dropdown.grid(row=0, column=0, padx=5, pady=5)

# Metrics display frame
metrics_frame = tk.Frame(ui_root)
metrics_frame.grid(row=2, column=0, padx=10, pady=10, sticky="w")

metric_labels = {}
for i, key in enumerate(latest_metrics.keys()):
    lbl = tk.Label(metrics_frame, text=f"{key}: --")
    lbl.grid(row=i, column=0, padx=5, pady=2, sticky="w")
    metric_labels[key] = lbl

# Save button
save_button = tk.Button(ui_root, text="Save Data", command=save_data)
save_button.grid(row=3, column=0, padx=10, pady=10, sticky="w")

init_db()
update_user_list()  # Populate user dropdown

scale_address = "FF:03:00:12:14:4B"  # Replace with your scale's MAC address
ble_thread = threading.Thread(target=start_ble_loop, args=(scale_address,), daemon=True)
ble_thread.start()

ui_root.mainloop()
