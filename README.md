
# README for Scale Metrics Application

---

## Overview

This project is a Python-based GUI application for managing and recording metrics from a Bluetooth-enabled smart scale. It integrates BLE communication, user profile management, and data storage for health metrics.

---

## Features

1. **Bluetooth Connectivity**:
   - Connects to a smart scale using BLE.
   - Reads metrics like weight, BMI, body fat percentage, and more.

2. **Database Integration**:
   - Stores user profiles and measurement data in an SQLite database.
   - Profiles include name, age, height, and gender.

3. **Real-Time Metrics Display**:
   - Displays latest metrics on the GUI.
   - Includes metrics like Body Fat %, Lean Body Mass, Metabolic Age, etc.

4. **Profile Management**:
   - Create and manage multiple user profiles.
   - Metrics are saved per user for detailed tracking.

5. **User-Friendly Interface**:
   - Built using `tkinter` for a simple and intuitive UI.
   - Dropdown menus for user selection and real-time updates.

---

## Prerequisites

- Python 3.8 or higher
- Libraries:
  - `asyncio`
  - `threading`
  - `tkinter`
  - `bleak` (for BLE communication)
  - `sqlite3`
- A Bluetooth-enabled smart scale with compatible UUIDs.
- Device MAC address for the scale.

---

## How to Run

1. **Install Dependencies**:
   Ensure all required Python libraries are installed:
   ```bash
   pip install bleak
   ```

2. **Set Up Database**:
   The application initializes the SQLite database (`metrics.db`) automatically on the first run.

3. **Configure the MAC Address**:
   Replace the `scale_address` variable in the script with your scale's MAC address:
   ```python
   scale_address = "XX:XX:XX:XX:XX:XX"
   ```

4. **Run the Application**:
   Execute the script:
   ```bash
   python main.py
   ```

---

## BLE Service Details

- **Service UUID**: `0000fff0-0000-1000-8000-00805f9b34fb`
- **Notify Characteristic UUID**: `0000fff1-0000-1000-8000-00805f9b34fb`
- **Write Characteristic UUID**: `0000fff2-0000-1000-8000-00805f9b34fb`

---

## Database Structure

- **Users Table**:
  - `id`: Primary Key
  - `name`, `age`, `height`, `gender`

- **Measurements Table**:
  - `id`: Primary Key
  - `user_id`: Foreign Key
  - `timestamp`: Measurement time
  - Metrics: `weight`, `BMI`, `body_fat`, etc.

---

## Known Issues

- The application assumes a fixed metric decoding format; ensure the scale supports this format.
- Ensure BLE notifications are enabled on the smart scale for data reading.

---

## Future Enhancements

1. Export metrics to CSV/Excel for analysis.
2. Add support for additional BLE-enabled devices.
3. Graphical trends of stored metrics.

---

## License

This project is licensed under the MIT License. See the LICENSE file for details.
