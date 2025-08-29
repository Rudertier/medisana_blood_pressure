"""Unit tests for the Medisana blood pressure Bluetooth device data.

This module validates the behavior of `MedisanaBPBluetoothDeviceData`,
including initialization, supported device detection, and unimplemented
methods.
"""

import asyncio
from types import SimpleNamespace

from custom_components.medisana_blood_pressure.medisana_bp import (
    MedisanaBPBluetoothDeviceData,
)
from custom_components.medisana_blood_pressure.medisana_bp.supported_devices import (
    MANUFACTURER_IDS,
    SUPPORTED_NAME_PREFIX,
    SUPPORTED_SERVICE_UUIDS,
)
import pytest

# Precompute constants to avoid repeated calls in decorators (fix RUF015)
_MANUFACTURER_IDS = list(MANUFACTURER_IDS)
_SUPPORTED_SERVICE_UUIDS = list(SUPPORTED_SERVICE_UUIDS)


@pytest.mark.asyncio
async def test_initialization():
    """Test that the device initializes with defaults and correct properties."""
    device = MedisanaBPBluetoothDeviceData()
    assert isinstance(device._event, asyncio.Event)
    assert device.title == "Medisana Blutdruckmesser"
    assert device.get_device_name() == "Medisana BP"


@pytest.mark.parametrize(
    "name,manufacturer_data,service_uuids,expected",
    [
        # Name matches prefix
        (f"{SUPPORTED_NAME_PREFIX}XYZ", {}, [], True),
        # Manufacturer ID matches
        ("UnknownName", {_MANUFACTURER_IDS[0]: b"\x00"}, [], True),
        # Service UUID matches
        ("UnknownName", {}, [_SUPPORTED_SERVICE_UUIDS[0]], True),
        # Nothing matches
        ("OtherName", {}, [], False),
        # Mixed: name wrong but manufacturer correct
        ("OtherName", {_MANUFACTURER_IDS[1]: b"\x01"}, [], True),
    ],
)
def test_supported(name, manufacturer_data, service_uuids, expected):
    """Test that the `supported` method detects compatible devices.

    Args:
        name: The advertised Bluetooth device name.
        manufacturer_data: Manufacturer-specific data dictionary.
        service_uuids: List of advertised service UUIDs.
        expected: Whether the device should be marked as supported.

    """
    device = MedisanaBPBluetoothDeviceData()

    # Create a mock BluetoothServiceInfo-like object
    service_info = SimpleNamespace(
        name=name,
        manufacturer_data=manufacturer_data,
        service_uuids=service_uuids,
    )

    result = device.supported(service_info)
    assert result == expected


def test_title_and_device_name():
    """Test that `title` and `get_device_name` return expected values."""
    device = MedisanaBPBluetoothDeviceData()
    assert device.title == "Medisana Blutdruckmesser"
    assert device.get_device_name() == "Medisana BP"
    # Optional: device_id param does not affect result
    assert device.get_device_name("anyid") == "Medisana BP"


def test_start_update_raises_notimplemented():
    """Test that `_start_update` raises `NotImplementedError` as expected."""
    device = MedisanaBPBluetoothDeviceData()
    service_info = SimpleNamespace(name="test")

    with pytest.raises(NotImplementedError):
        device._start_update(service_info)
