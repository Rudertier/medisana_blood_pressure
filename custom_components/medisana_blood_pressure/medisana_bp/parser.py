"""Parser for Medisana Bloodpressure devices."""

from __future__ import annotations

import asyncio
from datetime import datetime
import logging
import struct

from bluetooth_sensor_state_data import BluetoothData

_LOGGER = logging.getLogger(__name__)



class MedisanaBPBluetoothDeviceData(BluetoothData):
    """Data for MedisanaBP BLE sensors."""

    _event: asyncio.Event | None


    def __init__(self) -> None:
        super().__init__()
        self._event = asyncio.Event()
        _LOGGER.warning("Initializing MedisanaBPBluetoothDeviceData")

    def supported(self, service_info) -> bool:
        """Return True if this device is supported."""
        return service_info.name and service_info.name.startswith("1872B")

    @property
    def title(self):
        return "Medisana Blutdruckmesser"

    def get_device_name(self):
        return "Medisana BP"


def parse_blood_pressure(data: bytes) -> dict: #noqa PLR0915
    """Parse blood pressure data from Medisana BP."""
    offset = 0
    flags = data[offset]
    offset += 1

    result = {}

    # unit_kpa = (flags & 0x01) != 0
    time_stamp_present = (flags & 0x02) != 0
    pulse_rate_present = (flags & 0x04) != 0
    user_id_present = (flags & 0x08) != 0
    measurement_status_present = (flags & 0x10) != 0

    def parse_sfloat(b):
        raw = struct.unpack('<H', b)[0]
        mantissa = raw & 0x0FFF
        exponent = (raw & 0xF000) >> 12
        if exponent >= 0x8:#noqa PLR2004
            exponent = exponent - 0x10
        if mantissa >= 0x800: #noqa PLR2004
            mantissa = mantissa - 0x1000
        return mantissa * (10 ** exponent)

    result['systolic'] = parse_sfloat(data[offset:offset+2])
    offset += 2
    result['diastolic'] = parse_sfloat(data[offset:offset+2])
    offset += 2
    result['mean_arterial_pressure'] = parse_sfloat(data[offset:offset+2])
    offset += 2

    if time_stamp_present:
        year = struct.unpack('<H', data[offset:offset+2])[0]
        month = data[offset+2]
        day = data[offset+3]
        hour = data[offset+4]
        minute = data[offset+5]
        second = data[offset+6]
        offset += 7
        try:
            result['timestamp'] = datetime(year, month, day, hour, minute, second)
        except Exception as e:
            _LOGGER.warning(f"Ungültiger Zeitstempel in Daten: {e}")
            result['timestamp'] = None
    else:
        result['timestamp'] = None

    if pulse_rate_present:
        result['pulse_rate'] = parse_sfloat(data[offset:offset+2])
        offset += 2
    else:
        result['pulse_rate'] = None

    if user_id_present:
        result['user_id'] = data[offset]
        offset += 1
    else:
        result['user_id'] = None

    if measurement_status_present:
        result['measurement_status'] = struct.unpack('<H', data[offset:offset+2])[0]
        offset += 2
    else:
        result['measurement_status'] = None

    return result