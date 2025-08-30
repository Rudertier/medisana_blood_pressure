# 🩺 Medisana Blood Pressure Monitor Integration for Home Assistant

This custom integration enables Home Assistant to read measurements from a **Medisana Bluetooth Blood Pressure Monitor** (https://www.medisana.com/en/Health-control/Blood-pressure-monitor/). 
Big thanks to [@bkbilly](https://github.com/bkbilly) for his great work on [medisanabp_ble](https://github.com/bkbilly/medisanabp_ble) — I heavily relied on it for this project.

## ⚙️ Features
- Automatic detection of the blood pressure monitor when it becomes active
- Direct BLE connection using `BleakClient` to retrieve data
- No polling required – integration listens for BLE advertisements and reacts instantly
- Parses and exposes the following sensor data in Home Assistant:
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

Sometimes the synchronization fails; however, the data is **not lost**. 
It will be transferred the next time and stored in the attributes of the Last-Measurement sensor.

### 📡 Bluetooth Limitations  

This integration depends on Home Assistant’s Bluetooth stack to discover the Medisana blood pressure monitor. 
Once the device is discovered, Home Assistant currently ignores subsequent advertisement messages from the sensor, 
which means that no further callbacks are triggered. 
As a result, it may take an unpredictable amount of time before the integration receives new data, 
depending on when Home Assistant resets its Bluetooth discovery process. 
If you experience delays or missed readings, this is most likely the cause.  

## 📊 Example Automation

This example automation logs the latest measurements (systolic, diastolic, pulse, etc.) and sends them to a notification service.
All data, including missed measurements, is transferred to a CSV file.
You can adjust the `notify.blood_pressure` target to your preferred notification service.

```yaml
alias: Export blood pressure to csv
description: >
  Log the latest blood pressure measurements into a CSV-friendly message.
  Includes timestamp, systolic/diastolic pressure, mean arterial pressure,
  pulse, user id, status, RSSI, and battery level.
triggers:
  - trigger: state
    entity_id:
      - sensor.last_measurement
conditions: []
actions:
  - action: notify.send_message
    data:
      message: >
        {% for entry in states.sensor.last_measurement.attributes.values()
          | selectattr('timestamp', 'defined') | list %}
          {{ entry.systolic }}, {{ entry.diastolic }},
          {{ entry.mean_arterial_pressure }},
          {{ entry.timestamp.strftime('%Y-%m-%d %H:%M') }},
          {{ entry.pulse_rate }}, {{ entry.user_id }},
          {{ entry.measurement_status }}, {{ entry.rssi }},
          {{ entry.battery }}
        {% endfor %}
    target:
      entity_id: notify.blood_pressure
mode: single
```

## ✅ Supported Devices

Currently, this integration has been tested and confirmed to work with:

- **Medisana BU 570**
- **Medisana BU 546 connect**
- **Medisana BU 575**

If you successfully use this integration with another Medisana device, please open an issue or pull request to help extend the supported list.

## License

This project is licensed under the **Creative Commons Attribution-NonCommercial 4.0 International** license (CC BY-NC 4.0).  
You are free to use, modify, and share the code as long as it's **not for commercial purposes** and appropriate credit is given.

[View License](https://creativecommons.org/licenses/by-nc/4.0/)
