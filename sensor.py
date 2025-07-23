"""Sensor platform for Medisana Blood Pressure."""
from __future__ import annotations

from typing import Any
import asyncio
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfPressure, SIGNAL_STRENGTH_DECIBELS_MILLIWATT
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)
from bleak import BleakClient, BleakError
from homeassistant.components import bluetooth
from homeassistant.config_entries import ConfigEntry

import logging
from datetime import timedelta, datetime, UTC

from .const import DOMAIN, BP_MEASUREMENT_UUID,CHARACTERISTIC_BATTERY
from .medisana_bp import parser

_LOGGER = logging.getLogger(__name__)
WATCHDOG_TIMEOUT = timedelta(minutes=2)

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback
) -> None:
    """Set up Medisana blood pressure sensor from a config entry."""
    _LOGGER.warning(f"Sensor async_setup_entry: {entry}")

    coordinator: MedisanaCoordinator

    try:
        coordinator: MedisanaCoordinator = hass.data[DOMAIN][entry.entry_id]
    except KeyError:
        _LOGGER.error(f"No coordinator found for entry_id {entry.entry_id}")
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
            update_interval=None  # Polling nicht notwendig, BLE Push via Callback
        )
        self.mac_address = mac_address
        self._latest_value: dict | None = None
        self._last_seen: datetime | None = None
        self._parsed_data: dict | None = None
        self._rssi: int | None = None
        self._battery: int | None = None

        self.device_info = {            "identifiers": {("medisana_blood_pressure", self.mac_address)},
            "name": "Medisana Blood Pressure Monitor",
            "manufacturer": "Medisana",
            "model": "BP BLE Device",
        }

        self._unsub = bluetooth.async_register_callback(
            hass,
            self._bluetooth_callback,
            # None,
            bluetooth.BluetoothCallbackMatcher(address=self.mac_address),
            bluetooth.BluetoothScanningMode.ACTIVE,
        )

        _LOGGER.warning(f"Bluetooth callback registered for {self.mac_address}")
        _LOGGER.warning(f"Coordinator initialized: {id(self)}")

    def notification_handler(self, sender, data)->None:
        _LOGGER.warning(f"Notification from {sender}: {data.hex()}")
        parsed = parser.parse_blood_pressure(data)

        _LOGGER.warning(f"Parsed data: {parsed}")

        if self._latest_value is None:
            self._latest_value = {}

        if parsed is not None:
            self._latest_value[parsed['timestamp']] = parsed
            self._latest_value[parsed['timestamp']] ['rssi']=self._rssi
            self._latest_value[parsed['timestamp']] ['battery_level']=self._battery


        self._last_seen = datetime.now(UTC)
        _LOGGER.warning(f"notification_handler New value for self._latest_value: {self._latest_value}")
        self.async_set_updated_data(self._latest_value)


    async def connect_and_subscribe(self):
        """Connect to the device and subscribe to blood pressure notifications."""
        _LOGGER.warning(f"Connecting to {self.mac_address} to start notifications")

        try:
            async with BleakClient(self.mac_address) as client:
                if not client.is_connected:
                    _LOGGER.error(f"Failed to connect to {self.mac_address}")
                    return

                _LOGGER.warning(f"Connected to {self.mac_address}, subscribing to notifications")

                battery_char = client.services.get_characteristic(CHARACTERISTIC_BATTERY)
                battery_payload = await client.read_gatt_char(battery_char)
                self._battery = int(battery_payload[0])

                await client.start_notify(BP_MEASUREMENT_UUID, self.notification_handler)

                # Hier warten, sonst beendet HA sofort die Verbindung
                await asyncio.sleep(60)  # Z.B. 30 Sekunden warten auf Notifications

                await client.stop_notify(BP_MEASUREMENT_UUID)
                _LOGGER.warning(f"Stopped notifications for {self.mac_address}")
        except BleakError as error:
            _LOGGER.error(f"Failed to connect to {self.mac_address} {error}")
        except TimeoutError as error:
            _LOGGER.error(f"Timed out {self.mac_address} {error}")


    @callback
    def _bluetooth_callback(self, service_info: bluetooth.BluetoothServiceInfoBleak, _: Any) -> None:
        _LOGGER.warning(f"BLE device data received from{service_info.address}")
        _LOGGER.warning(f"Got service_info: {service_info}")

        self._rssi = service_info.rssi
        self.hass.async_create_task(self.connect_and_subscribe())


        _LOGGER.warning(f"Parsed Data in callback: {self._parsed_data}")




    async def _async_update_data(self) -> int | None:
        """Fetch latest data."""
        _LOGGER.warning(f"_async_update_data returning {self._latest_value}")
        return self._latest_value


    async def async_will_remove_from_hass(self):
        """Cleanup on unload."""
        if self._unsub:
            self._unsub()
            self._unsub = None

        _LOGGER.warning(f"Unsubscribed BLE callback for {self.mac_address}")


class MbpsMeanArterial(CoordinatorEntity, SensorEntity):
    """Representation of the Medisana Blood Pressure sensor."""

    _attr_name = "Mean Arterial Pressure"
    _attr_device_class = SensorDeviceClass.PRESSURE
    _attr_native_unit_of_measurement = UnitOfPressure.MMHG
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: MedisanaCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"medisana_bp_mean_arterial_{coordinator.mac_address}"
        self._native_value: int | None = None
        self.device_info= coordinator.device_info

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update the sensor with the latest value."""
        _LOGGER.warning(f"_handle_coordinator_update Mean Arterial Pressure: {self.coordinator.data}")
        if self.coordinator.data is None:
            return

        key = max(self.coordinator.data.keys())
        mean_arterial_pressure = self.coordinator.data[key].get("mean_arterial_pressure")

        if mean_arterial_pressure is not None:
            self._native_value = mean_arterial_pressure
            _LOGGER.warning(f"mean_arterial_pressure level updated: {self._native_value}%")
        else:
            _LOGGER.warning("mean_arterial_pressure level not available in the latest data")

        self.async_write_ha_state()

    @property
    def native_value(self) -> int | None:
        return self._native_value


class MbpsRssi(CoordinatorEntity, SensorEntity):
    """Representation of the Medisana Blood Pressure sensor."""


    _attr_name = "Signal Strength"
    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: MedisanaCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"medisana_bp_rssi_{coordinator.mac_address}"
        self._native_value: int | None = None
        self.device_info= coordinator.device_info

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update the sensor with the latest value."""
        _LOGGER.warning(f"_handle_coordinator_update Signal Strength: {self.coordinator.data}")
        if self.coordinator.data is None:
            return

        key = max(self.coordinator.data.keys())
        rssi = self.coordinator.data[key].get("rssi")
        self._native_value = rssi

        if rssi is not None:
            _LOGGER.warning(f"rssi level updated: {self._native_value}%")
        else:
            _LOGGER.warning("rssi level not available in the latest data")
        self.async_write_ha_state()

    @property
    def native_value(self) -> int | None:
        return self._native_value


class MbpsPulse(CoordinatorEntity, SensorEntity):
    """Representation of the Medisana Blood Pressure sensor."""

    _attr_name = "Heart Rate"
    _attr_device_class = SensorDeviceClass.FREQUENCY
    _attr_native_unit_of_measurement = 'bpm'
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: MedisanaCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"medisana_bp_heart_rate_{coordinator.mac_address}"
        self._native_value: int | None = None
        self.device_info= coordinator.device_info

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update the sensor with the latest value."""
        if self.coordinator.data is None:
            return
        key = max(self.coordinator.data.keys())
        pulse_rate = self.coordinator.data[key].get("pulse_rate")

        if pulse_rate is not None:
            self._native_value = pulse_rate
            _LOGGER.warning(f"pulse_rate level updated: {self._native_value}%")
        else:
            _LOGGER.warning("pulse_rate level not available in the latest data")

        self.async_write_ha_state()

    @property
    def native_value(self) -> int | None:
        return self._native_value



class MbpsSystolic(CoordinatorEntity, SensorEntity):
    """Representation of the Medisana Blood Pressure sensor."""

    _attr_name = "Systolic Pressure"
    _attr_device_class = SensorDeviceClass.PRESSURE
    _attr_native_unit_of_measurement = UnitOfPressure.MMHG
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: MedisanaCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"medisana_bp_systolic_{coordinator.mac_address}"
        self._native_value: int | None = None
        self.device_info= coordinator.device_info

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update the sensor with the latest value."""
        if self.coordinator.data is None:
            return
        key = max(self.coordinator.data.keys())
        systolic = self.coordinator.data[key].get("systolic")

        if systolic is not None:
            self._native_value = systolic
            _LOGGER.warning(f"systolic level updated: {self._native_value}%")
        else:
            _LOGGER.warning("systolic level not available in the latest data")

        self.async_write_ha_state()

    @property
    def native_value(self) -> int | None:
        return self._native_value




class MbpsDiastolic(CoordinatorEntity, SensorEntity):
    """Representation of the Medisana Blood Pressure sensor."""

    _attr_name = "Diastolic Pressure"
    _attr_device_class = SensorDeviceClass.PRESSURE
    _attr_native_unit_of_measurement = UnitOfPressure.MMHG
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: MedisanaCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"medisana_bp_diastolic_{coordinator.mac_address}"
        self._native_value: int | None = None
        self.device_info= coordinator.device_info

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update the sensor with the latest value."""
        if self.coordinator.data is None:
            return
        key = max(self.coordinator.data.keys())
        diastolic = self.coordinator.data[key].get("diastolic")

        if diastolic is not None:
            self._native_value = diastolic
            _LOGGER.warning(f"diastolic level updated: {self._native_value}%")
        else:
            _LOGGER.warning("diastolic level not available in the latest data")

        self.async_write_ha_state()

    @property
    def native_value(self) -> int | None:
        return self._native_value

class MbpsUserId(CoordinatorEntity, SensorEntity):
    """Representation of the Medisana Blood Pressure sensor."""

    _attr_name = "User Id"
    _attr_device_class = None
    _attr_native_unit_of_measurement = None
    _attr_state_class = None

    def __init__(self, coordinator: MedisanaCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"medisana_bp_user_id_{coordinator.mac_address}"
        self._native_value: int | None = None
        self.device_info= coordinator.device_info
    @callback
    def _handle_coordinator_update(self) -> None:
        """Update the sensor with the latest value."""
        if self.coordinator.data is None:
            return
        key = max(self.coordinator.data.keys())


        user_id = self.coordinator.data[key].get("user_id")

        if user_id is not None:
            self._native_value = user_id
            _LOGGER.warning(f"user_id level updated: {self._native_value}%")
        else:
            _LOGGER.warning("user_id level not available in the latest data")

        self.async_write_ha_state()

    @property
    def native_value(self) -> int | None:
        return self._native_value





class MbpsLastMeasurement(CoordinatorEntity, SensorEntity):
    """Representation of the Medisana Blood Pressure sensor."""

    _attr_name = "Last Measurement"
    _attr_device_class = None
    _attr_native_unit_of_measurement = None
    _attr_state_class = None

    def __init__(self, coordinator: MedisanaCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"medisana_bp_timestamp_{coordinator.mac_address}"
        self._native_value: int | None = None
        self.device_info= coordinator.device_info

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update the sensor with the latest value."""
        if self.coordinator.data is None:
            return

        key = max(self.coordinator.data.keys())

        if key is not None:
            self._native_value = key

        self.async_write_ha_state()

    @property
    def native_value(self) -> int | None:
        return self._native_value

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes."""
        return self.coordinator.data




class MbpsBattery(CoordinatorEntity, SensorEntity):
    """Representation of the Medisana Blood Pressure Battery Level sensor."""

    _attr_name = "Battery Level"
    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_native_unit_of_measurement = "%"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: MedisanaCoordinator) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"medisana_bp_battery_{coordinator.mac_address}"
        self._native_value: int | None = None
        self.device_info= coordinator.device_info

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update the battery sensor with the latest value."""

        if not self.coordinator.data:
            _LOGGER.warning("No data available for battery sensor update")
            return

        key = max(self.coordinator.data.keys())
        battery = self.coordinator.data[key].get("battery_level")

        if battery is not None:
            self._native_value = battery
            _LOGGER.warning(f"Battery level updated: {self._native_value}%")
        else:
            _LOGGER.warning("Battery level not available in the latest data")

        self.async_write_ha_state()

    @property
    def native_value(self) -> int | None:
        return self._native_value

