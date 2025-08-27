"""Supported Medisana Blood Pressure devices.

Defines name prefixes and service UUIDs used to detect compatible devices.
"""

SUPPORTED_NAME_PREFIX = "1872B"

SUPPORTED_SERVICE_UUIDS = {
    "0000fcf1-0000-1000-8000-00805f9b34fb",
    "0000fd69-0000-1000-8000-00805f9b34fb",
    "00001810-0000-1000-8000-00805f9b34fb",  # Standard Blood Pressure Service
}
