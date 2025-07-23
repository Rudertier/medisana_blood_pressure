"""Medisana Blood Pressure BLE integration."""
from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .sensor import MedisanaCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up via configuration.yaml (nicht verwendet)."""
    return True  # Oder False, wenn du nur config flow unterstützen möchtest


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Medisana Blood Pressure BLE from a config entry."""
    _LOGGER.warning(f"Setting up config entry for {DOMAIN}")

    hass.data.setdefault(DOMAIN, {})

    mac_address = str(entry.unique_id).upper()
    coordinator = MedisanaCoordinator(hass, mac_address)
    hass.data[DOMAIN][entry.entry_id] = coordinator

    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, ["sensor"])
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    coordinator: MedisanaCoordinator = hass.data[DOMAIN].get(entry.entry_id)
    if coordinator:
        await coordinator.async_will_remove_from_hass()

    unload_ok = await hass.config_entries.async_forward_entry_unload(entry, "sensor")
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)

    return unload_ok
