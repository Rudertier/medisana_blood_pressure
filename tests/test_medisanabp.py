import asyncio
import pytest
from types import SimpleNamespace

from custom_components.medisana_blood_pressure.medisana_bp import (
    MedisanaBPBluetoothDeviceData,
)
from custom_components.medisana_blood_pressure.medisana_bp.supported_devices import (
    SUPPORTED_NAME_PREFIX,
    SUPPORTED_SERVICE_UUIDS,
    MANUFACTURER_IDS,
)


@pytest.mark.asyncio
async def test_initialization():
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
        ("UnknownName", {list(MANUFACTURER_IDS)[0]: b"\x00"}, [], True),
        # Service UUID matches
        ("UnknownName", {}, [list(SUPPORTED_SERVICE_UUIDS)[0]], True),
        # Nothing matches
        ("OtherName", {}, [], False),
        # Mixed: name wrong but manufacturer correct
        ("OtherName", {list(MANUFACTURER_IDS)[1]: b"\x01"}, [], True),
    ],
)
def test_supported(name, manufacturer_data, service_uuids, expected):
    device = MedisanaBPBluetoothDeviceData()

    # Create a mock BluetoothServiceInfo object
    service_info = SimpleNamespace(
        name=name,
        manufacturer_data=manufacturer_data,
        service_uuids=service_uuids,
    )

    result = device.supported(service_info)
    assert result == expected


def test_title_and_device_name():
    device = MedisanaBPBluetoothDeviceData()
    assert device.title == "Medisana Blutdruckmesser"
    assert device.get_device_name() == "Medisana BP"
    # Optional: device_id param does not affect result
    assert device.get_device_name("anyid") == "Medisana BP"


def test_start_update_raises_notimplemented():
    device = MedisanaBPBluetoothDeviceData()
    service_info = SimpleNamespace(name="test")

    with pytest.raises(NotImplementedError):
        device._start_update(service_info)
