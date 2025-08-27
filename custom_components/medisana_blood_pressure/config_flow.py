"""Config flow for MedisanaBP BLE integration."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.bluetooth import (
    BluetoothServiceInfoBleak,
    async_discovered_service_info,
)
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import CONF_ADDRESS
import voluptuous as vol

from .const import DOMAIN
from .medisana_bp import MedisanaBPBluetoothDeviceData

_LOGGER = logging.getLogger(__name__)

class MedisanaBPConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for MedisanaBP."""

    VERSION = 1

    def __init__(self) -> None:
        """Initialize the config flow."""
        _LOGGER.info("MedisanaBPConfigFlow initialized")
        self._discovery_info: BluetoothServiceInfoBleak | None = None
        self._discovered_device: MedisanaBPBluetoothDeviceData | None = None
        self._discovered_devices: dict[str, str] = {}

    async def async_step_bluetooth(
        self, discovery_info: BluetoothServiceInfoBleak
    ) -> ConfigFlowResult:
        """Handle the bluetooth discovery step."""
        _LOGGER.debug("MedisanaBPConfigFlow async_step_bluetooth")
        await self.async_set_unique_id(discovery_info.address)
        self._abort_if_unique_id_configured()
        device = MedisanaBPBluetoothDeviceData()
        if not device.supported(discovery_info):
            _LOGGER.warning(f"Device {discovery_info} is not supported")
            return self.async_abort(reason="not_supported")
        self._discovery_info = discovery_info
        self._discovered_device = device
        return await self.async_step_bluetooth_confirm()

    async def async_step_bluetooth_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Confirm discovery."""
        _LOGGER.debug("MedisanaBPConfigFlow async_step_bluetooth_confirm")
        assert self._discovered_device is not None
        device = self._discovered_device
        assert self._discovery_info is not None
        discovery_info = self._discovery_info
        title = device.title or device.get_device_name() or discovery_info.name
        if user_input is not None:
            return self.async_create_entry(title=title, data={})

        self._set_confirm_only()
        placeholders = {"name": title}
        self.context["title_placeholders"] = placeholders
        return self.async_show_form(
            step_id="bluetooth_confirm", description_placeholders=placeholders
        )

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the user step to pick discovered device."""
        _LOGGER.debug("MedisanaBPConfigFlow async_step_user")
        if user_input is not None:
            address = user_input[CONF_ADDRESS]
            await self.async_set_unique_id(address, raise_on_progress=False)
            self._abort_if_unique_id_configured()
            return self.async_create_entry(
                title=self._discovered_devices[address], data={}
            )

        current_addresses = self._async_current_ids()
        for discovery_info in async_discovered_service_info(self.hass,connectable= False):
            address = discovery_info.address
            if address in current_addresses or address in self._discovered_devices:
                continue
            device = MedisanaBPBluetoothDeviceData()
            if device.supported(discovery_info):
                self._discovered_devices[address] = (
                    device.title or device.get_device_name() or discovery_info.name
                )

        if not self._discovered_devices:
            _LOGGER.debug("No discovered devices found")
            return self.async_abort(reason="no_devices_found")

        _LOGGER.debug("Wait for User")
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {vol.Required(CONF_ADDRESS): vol.In(self._discovered_devices)}
            ),
        )