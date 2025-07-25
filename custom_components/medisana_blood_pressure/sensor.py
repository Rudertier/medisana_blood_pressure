"""Sensor platform for Medisana Blood Pressure."""
from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
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
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.update_coordinator import (
    CoordinatorEntity,
    DataUpdateCoordinator,
)

from .const import BP_MEASUREMENT_UUID, CHARACTERISTIC_BATTERY, DOMAIN
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
            update_interval=None  # Polling nicht notwendig, BLE Push via Callback
        )
        self.mac_address = mac_address
        self._latest_value: dict  = {}
        self._last_seen: datetime | None = None
        self._parsed_data: dict | None = None
        self._rssi: int | None = None
        self._battery: int | None = None

        self.device_info = {            "identifiers": {("medisana_blood_pressure", self.mac_address)},
            "name": "Medisana Blood Pressure Monitor",
            "manufacturer": "Medisana",
            "model": "BP BLE Device",
        }

        self._unsub:Callable|None = bluetooth.async_register_callback(
            hass,
            self._bluetooth_callback,
            # None,
            bluetooth.BluetoothCallbackMatcher(address=self.mac_address),
            bluetooth.BluetoothScanningMode.ACTIVE,
        )

        _LOGGER.warning(f"Bluetooth callback registered for {self.mac_address}")
        _LOGGER.warning(f"Coordinator initialized: {id(self)}")

    def notification_handler(self, sender:BleakGATTCharacteristic, data:bytearray)->None:
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


    async def connect_and_subscribe(self)->None:
        """Connect to the device and subscribe to blood pressure notifications."""
        _LOGGER.warning(f"Connecting to {self.mac_address} to start notifications")

        try:
            async with BleakClient(self.mac_address) as client:
                if not client.is_connected:
                    _LOGGER.error(f"Failed to connect to {self.mac_address}")
                    return

                _LOGGER.warning(f"Connected to {self.mac_address}, subscribing to notifications")

                battery_char = client.services.get_characteristic(CHARACTERISTIC_BATTERY)
                battery_payload = await client.read_gatt_char(battery_char) if battery_char else [0]
                self._battery = int(battery_payload[0])

                await client.start_notify(BP_MEASUREMENT_UUID, self.notification_handler)

                # Hier warten, sonst beendet HA sofort die Verbindung
                await asyncio.sleep(60)  # Z.B. 30 Sekunden warten auf Notifications

                await client.stop_notify(BP_MEASUREMENT_UUID)
                _LOGGER.warning(f"Stopped notifications for {self.mac_address}")
        except BleakError as error:
            _LOGGER.warning(f"Failed to connect to {self.mac_address} {error}")
        except TimeoutError as error:
            _LOGGER.warning(f"Timed out {self.mac_address} {error}")


    @callback
    def _bluetooth_callback(self, service_info: bluetooth.BluetoothServiceInfoBleak, _: Any) -> None:
        _LOGGER.warning(f"BLE device data received from{service_info.address}")
        _LOGGER.warning(f"Got service_info: {service_info}")

        self._rssi = service_info.rssi
        self.hass.async_create_task(self.connect_and_subscribe())


        _LOGGER.warning(f"Parsed Data in callback: {self._parsed_data}")




    async def _async_update_data(self) -> dict[Any,Any]:
        """Fetch latest data."""
        _LOGGER.warning(f"_async_update_data returning {self._latest_value}")
        return self._latest_value


    async def async_will_remove_from_hass(self)->None:
        """Cleanup on unload."""
        if self._unsub:
            self._unsub()
            self._unsub = None

        _LOGGER.warning(f"Unsubscribed BLE callback for {self.mac_address}")


class MedisanaRestoreSensor(CoordinatorEntity, SensorEntity, RestoreEntity):
    """Basisklasse für Medisana-Sensoren mit RestoreEntity-Unterstützung."""

    def __init__(#noqa plr0913
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
        self._native_value: int | None = None
        self._data_key = data_key
        self.device_info = coordinator.device_info

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()

        if self._native_value is not None:
            return

        state = await self.async_get_last_state()
        if state and state.state not in (None, "unknown", "unavailable"):
            try:
                self._native_value = int(state.state)
                _LOGGER.debug(f"[Restore] {self._attr_name} restored value: {self._native_value}")
            except ValueError:
                _LOGGER.warning(f"[Restore] Failed to restore {self._attr_name} from {state.state}")

    @callback
    def _handle_coordinator_update(self) -> None:
        if not self.coordinator.data:
            return

        key = max(self.coordinator.data.keys())
        value = self.coordinator.data[key].get(self._data_key)

        if value is not None:
            self._native_value = value
            _LOGGER.debug(f"[Update] {self._attr_name} updated: {self._native_value}")
        else:
            _LOGGER.debug(f"[Update] {self._attr_name} not available in data")

        self.async_write_ha_state()

    @property
    def native_value(self) -> int | None:
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
        self.device_info= coordinator.device_info

    @callback
    def _handle_coordinator_update(self) -> None:
        """Update the sensor with the latest value."""
        if self.coordinator.data is None:
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



