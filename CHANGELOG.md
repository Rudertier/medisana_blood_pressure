# Changelog

All notable changes to this project will be documented in this file.

## [0.2.0] – 2025-08-26
### Added
- Initial public release of the Medisana Blood Pressure Monitor integration.
- Automatic BLE detection of Medisana BP monitors.
- Sensors for systolic, diastolic, mean arterial pressure, heart rate, user ID, battery, RSSI, and last measurement timestamp.
- Local push integration reacting to BLE advertisements instead of polling.
- Last Measurement sensor stores all historical data in attributes, including missed measurements.
- Example automation to log measurements to CSV or notification service.

### Notes
- The device is only reachable for a short time after a measurement.
- Missed measurements are captured and stored on the next connection.
