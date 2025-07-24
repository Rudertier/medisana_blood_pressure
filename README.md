# MedisanaBloodPressure Sensor
Integrates Bluetooth LE (https://www.medisana.com/en/Health-control/Blood-pressure-monitor/) to Home Assistant using active connection to get infromation from the sensors.

Exposes the following sensors:
 - Diastolic pressure
 - Systolic pressure
 - Mean arterial pressure
 - Pulses
 - Measured date (With historic data)
 - User-Id
 - Battery
 - Bluetooth RSSI

Big thanks to [@bkbilly](https://github.com/bkbilly) for his great work on [medisanabp_ble](https://github.com/bkbilly/medisanabp_ble) — I heavily relied on it for this project.
