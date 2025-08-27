"""Sensor platform for Medisana Blood Pressure."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime
import logging
from typing import Any

from bleak import BleakClient, BleakError, BleakGATTCharacteristic
from homeassistant.components import bluetooth
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import SIGNAL_STRENGTH_DECIBELS_MILLIWATT, UnitOfPressure
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import BP_MEASUREMENT_UUID, CHARACTERISTIC_BATTERY, DOMAIN
from .medisana_bp import helpers, parser

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
        hass: HomeAssistant,
        entry: ConfigEntry,
        async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Medisana blood pressure sensor from a config entry."""
    _LOGGER.info(f"Sensor async_setup_entry: {entry}")

    try:
        coordinator: MedisanaCoordinator = hass.data[DOMAIN][entry.entry_id]
    except KeyError:
        _LOGGER.exception(f"No coordinator found for entry_id {entry.entry_id}")
        return
    async_add_entities([MbpsMeanArterial(coordinator),
                        MbpsRssi(coordinator),
                        MbpsPulse(coordinator),
                        MbpsSystolic(coordinator),
                        MbpsDiastolic(coordinator),
                        MbpsUserId(coordinator),
                        MbpsLastMeasurement(coordinator),
                        MbpsBattery(coordinator)])


class MedisanaCoordinator(DataUpdateCoordinator):
    """Coordinator to manage Medisana BLE updates."""

    def __init__(self, hass: HomeAssistant, mac_address: str):
        super().__init__(
            hass,
            _LOGGER,
            name="Medisana Blood Pressure Coordinator",
            update_interval=None  # Polling not necessary, BLE Push via Callback
        )
        self.mac_address = mac_address
        self._latest_value: dict = {}
        self._last_seen: datetime | None = None
        self._parsed_data: dict | None = None
        self._rssi: int | None = None
        self._battery: int | None = None

        self.device_info: DeviceInfo = DeviceInfo(manufacturer="Medisana",
                                                  model="BP BLE Device",
                                                  name="Medisana Blood Pressure Monitor",
                                                  serial_number=None,
                                                  identifiers={("medisana_blood_pressure", self.mac_address)},
                                                  )
        self._unsub: Callable[[], None] | None = None
        self._unsub = bluetooth.async_register_callback(
            hass,
            self._bluetooth_callback,
            # None,
            bluetooth.BluetoothCallbackMatcher(address=self.mac_address),
            bluetooth.BluetoothScanningMode.ACTIVE,
        )

        _LOGGER.debug(f"Coordinator initialized: {id(self)}")

    def notification_handler(self, sender: BleakGATTCharacteristic, data: bytearray) -> None:
        _LOGGER.debug(f"Notification from {sender}: {data.hex()}")
        parsed = parser.parse_blood_pressure(data)

        _LOGGER.debug(f"Parsed data: {parsed}")

        if self._latest_value is None:
            self._latest_value = {}

        if parsed is not None:
            self._latest_value[parsed['timestamp']] = parsed
            self._latest_value[parsed['timestamp']]['rssi'] = self._rssi
            self._latest_value[parsed['timestamp']]['battery'] = self._battery

        self._last_seen = datetime.now(UTC)
        _LOGGER.debug(f"notification_handler New value for self._latest_value: {self._latest_value}")
        self.async_set_updated_data(self._latest_value)

    async def connect_and_subscribe(self) -> None:
        """Connect to the device and subscribe to blood pressure notifications."""
        _LOGGER.info(f"Connecting to {helpers.mask_mac(self.mac_address)} to start notifications")

        try:
            async with BleakClient(self.mac_address) as client:
                if not client.is_connected:
                    _LOGGER.error(f"Failed to connect to {helpers.mask_mac(self.mac_address)}")
                    return

                _LOGGER.debug(f"Connected to {helpers.mask_mac(self.mac_address)}, subscribing to notifications")

                battery_char = client.services.get_characteristic(CHARACTERISTIC_BATTERY)
                battery_payload = await client.read_gatt_char(battery_char) if battery_char else [0]
                self._battery = int(battery_payload[0])

                await client.start_notify(BP_MEASUREMENT_UUID, self.notification_handler)

                # Need to wait, else HA will terminate the connection
                await asyncio.sleep(60)

                await client.stop_notify(BP_MEASUREMENT_UUID)
                _LOGGER.debug(f"Stopped notifications for {helpers.mask_mac(self.mac_address)}")

        except BleakError:
            _LOGGER.exception(f"Failed to connect to Medisana Blood Pressure device "
                              f"{helpers.mask_mac(self.mac_address)}")
        except TimeoutError:
            _LOGGER.exception(f"Connection attempt to Medisana Blood Pressure device timed out "
                              f"{helpers.mask_mac(self.mac_address)}")

    @callback
    def _bluetooth_callback(self, service_info: bluetooth.BluetoothServiceInfoBleak, _: Any) -> None:
        _LOGGER.debug(f"BLE device data received from: {service_info.address}")
        _LOGGER.debug(f"Got service_info: {service_info}")

        self._rssi = service_info.rssi
        self.hass.async_create_task(self.connect_and_subscribe())

        _LOGGER.debug(f"Parsed Data in callback: {self._parsed_data}")

    async def _async_update_data(self) -> dict[Any, Any]:
        """Fetch latest data."""
        _LOGGER.debug(f"_async_update_data returning {self._latest_value}")
        return self._latest_value

    async def async_will_remove_from_hass(self) -> None:
        """Cleanup on unload."""
        if self._unsub is not None:
            self._unsub()
            self._unsub = None

        _LOGGER.debug(f"Unsubscribed BLE callback for {helpers.mask_mac(self.mac_address)}")


class MedisanaRestoreSensor(CoordinatorEntity, SensorEntity, RestoreEntity):
    """Base class for Medisana-Sensors with RestoreEntity-Capability."""

    def __init__(  # noqa plr0913
            self,
            coordinator: MedisanaCoordinator,
            name: str,
            unique_id_suffix: str,
            data_key: str,
            unit: str | None = None,
            device_class: SensorDeviceClass | None = None,
            state_class: SensorStateClass | None = SensorStateClass.MEASUREMENT,
    ) -> None:
        super().__init__(coordinator)
        self._attr_name = name
        self._attr_unique_id = f"medisana_bp_{unique_id_suffix}_{coordinator.mac_address}"
        self._attr_native_unit_of_measurement = unit
        self._attr_device_class = device_class
        self._attr_state_class = state_class
        self._native_value: int | str | float | None = None
        self._data_key = data_key
        self.device_info = coordinator.device_info

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        if self._native_value is not None:
            return

        state = await self.async_get_last_state()
        if state and state.state not in (None, "unknown", "unavailable"):
            try:
                self._native_value = state.state
            except ValueError:
                _LOGGER.exception(f"Failed to restore {self._attr_name} from {state.state}")

    @callback
    def _handle_coordinator_update(self) -> None:
        if not self.coordinator.data:
            _LOGGER.warning("No data received from coordinator")
            return

        key = max(self.coordinator.data.keys())
        value = self.coordinator.data[key].get(self._data_key)

        if value is not None:
            self._native_value = value
            _LOGGER.debug(f"Update {self._attr_name} updated: {self._native_value}")
        else:
            _LOGGER.warning(f"Update {self._attr_name} not available in data")

        self.async_write_ha_state()

    @property
    def native_value(self) -> int | str | float | None:
        return self._native_value


class MbpsBattery(MedisanaRestoreSensor):
    """Sensor containing Battery data."""

    def __init__(self, coordinator: MedisanaCoordinator) -> None:
        super().__init__(
            coordinator,
            name="Battery Level",
            unique_id_suffix="battery",
            data_key="battery",
            unit='%',
            device_class=SensorDeviceClass.BATTERY,
        )


class MbpsSystolic(MedisanaRestoreSensor):
    """Sensor containing the systolic blood pressure in mmHg."""

    def __init__(self, coordinator: MedisanaCoordinator) -> None:
        super().__init__(
            coordinator,
            name="Systolic Pressure",
            unique_id_suffix="systolic",
            data_key="systolic",
            unit=UnitOfPressure.MMHG,
            device_class=SensorDeviceClass.PRESSURE,
        )


class MbpsDiastolic(MedisanaRestoreSensor):
    """Sensor containing the diastolic blood pressure in mmHg."""

    def __init__(self, coordinator: MedisanaCoordinator) -> None:
        super().__init__(
            coordinator,
            name="Diastolic Pressure",
            unique_id_suffix="diastolic",
            data_key="diastolic",
            unit=UnitOfPressure.MMHG,
            device_class=SensorDeviceClass.PRESSURE,
        )


class MbpsMeanArterial(MedisanaRestoreSensor):
    """Sensor containing the mean arterial blood pressure in mmHg."""

    def __init__(self, coordinator: MedisanaCoordinator) -> None:
        super().__init__(
            coordinator,
            name="Mean Arterial Pressure",
            unique_id_suffix="mean_arterial",
            data_key="mean_arterial_pressure",
            unit=UnitOfPressure.MMHG,
            device_class=SensorDeviceClass.PRESSURE,
        )


class MbpsPulse(MedisanaRestoreSensor):
    """Sensor containing the heart rate bpm."""

    def __init__(self, coordinator: MedisanaCoordinator) -> None:
        super().__init__(
            coordinator,
            name="Heart Rate",
            unique_id_suffix="pulse",
            data_key="pulse_rate",
            unit="bpm",
            device_class=SensorDeviceClass.FREQUENCY,
        )


class MbpsRssi(MedisanaRestoreSensor):
    """Sensor containing the signal strength."""

    def __init__(self, coordinator: MedisanaCoordinator) -> None:
        super().__init__(
            coordinator,
            name="Signal Strength",
            unique_id_suffix="rssi",
            data_key="rssi",
            unit=SIGNAL_STRENGTH_DECIBELS_MILLIWATT,
            device_class=SensorDeviceClass.SIGNAL_STRENGTH,
        )


class MbpsUserId(MedisanaRestoreSensor):
    """Sensor containing the user id."""

    def __init__(self, coordinator: MedisanaCoordinator) -> None:
        super().__init__(
            coordinator,
            name="User Id",
            unique_id_suffix="user_id",
            data_key="user_id",
            unit=None,
            device_class=None,
            state_class=None,
        )


class MbpsLastMeasurement(CoordinatorEntity, SensorEntity):
    """Sensor containing the last measurement time and the data transferred."""

    _attr_name = "Last Measurement"
    _attr_device_class = None
    _attr_native_unit_of_measurement = None
    _attr_state_class = None

    def __init__(self, coordinator: MedisanaCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"medisana_bp_timestamp_{coordinator.mac_address}"
        self._native_value: str | None = None
        self.device_info = coordinator.device_info

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update the sensor with the latest value."""
        if not self.coordinator.data:
            _LOGGER.warning("No data received in MbpsLastMeasurement")
            return

        key = max(self.coordinator.data.keys())

        if key is not None:
            self._native_value = str(key)

        self.async_write_ha_state()

    @property
    def native_value(self) -> str | None:
        return self._native_value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return self.coordinator.data
