# 🩺 Medisana Blood Pressure Monitor Integration for Home Assistant

This custom integration enables Home Assistant to read measurements from a **Medisana Bluetooth Blood Pressure Monitor** (https://www.medisana.com/en/Health-control/Blood-pressure-monitor/). 
Big thanks to [@bkbilly](https://github.com/bkbilly) for his great work on [medisanabp_ble](https://github.com/bkbilly/medisanabp_ble) — I heavily relied on it for this project.

## ⚙️ Features
- Automatic detection of the blood pressure monitor when active
- Connects via BLE to retrieve data using `BleakClient`
- Parses and exposes the following sensor data:
  - Systolic Pressure
  - Diastolic Pressure
  - Mean Arterial Pressure
  - Heart Rate
  - User ID
  - Battery Level
  - Signal Strength (RSSI)
  - Timestamp of Last Measurement

## 🧠 Conception

The Medisana Blood Pressure Monitor is only **active and reachable for a short period** after a measurement is completed.  
To accommodate this, the integration is implemented as a **`local_push`** integration.

It does **not poll** the device regularly—instead, it **reacts to BLE advertisements** and pulls data immediately when available.

- The Medisana Blood Pressure Monitor sends **advertising** data over bluetooth.
- Home Assistan receives BLE advertisement and triggers the integrations  `_bluetooth_callback` function.
- The integration connects to device using BleakClient and subscribes to blood pressure measurement characteristics
- The received *GATT Notification Received* is then processed by the `notification_handler` which parses and stores the data
- The Coordinator broadcasts update to all sensor entities, which recieve the data (`_handle_coordinator_update`) and update their own state

## License

This project is licensed under the **Creative Commons Attribution-NonCommercial 4.0 International** license (CC BY-NC 4.0).  
You are free to use, modify, and share the code as long as it's **not for commercial purposes** and appropriate credit is given.

[View License](https://creativecommons.org/licenses/by-nc/4.0/)
