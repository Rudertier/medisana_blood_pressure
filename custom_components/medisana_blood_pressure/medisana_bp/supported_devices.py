"""Constants for supported Medisana Blood Pressure devices."""

# Device name prefix
SUPPORTED_NAME_PREFIX = "1872B"

# Known service UUIDs for supported devices (lowercase)
SUPPORTED_SERVICE_UUIDS = {
    "0000fcf1-0000-1000-8000-00805f9b34fb",  # Vendor-specific
    "0000fd69-0000-1000-8000-00805f9b34fb",  # Vendor-specific
    "00001810-0000-1000-8000-00805f9b34fb",  # Standard Blood Pressure Service
    "00002a35-0000-1000-8000-00805f9b34fb",  # Blood Pressure Measurement characteristic
}
# Known manufacturer ids for supported devices
MANUFACTURER_IDS = {18498, 31256}