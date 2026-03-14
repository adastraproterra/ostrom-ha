"""The Ostrom integration."""
from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_ARBEITSPREIS,
    CONF_CLIENT_ID,
    CONF_CLIENT_SECRET,
    CONF_ENVIRONMENT,
    CONF_ZIP_CODE,
    DOMAIN,
    ENV_PRODUCTION,
)
from .coordinator import OstromCoordinator

PLATFORMS = ["sensor"]

type OstromConfigEntry = ConfigEntry[OstromCoordinator]


async def async_setup_entry(hass: HomeAssistant, entry: OstromConfigEntry) -> bool:
    """Set up Ostrom from a config entry."""
    coordinator = OstromCoordinator(
        hass,
        client_id=entry.data[CONF_CLIENT_ID],
        client_secret=entry.data[CONF_CLIENT_SECRET],
        zip_code=entry.data[CONF_ZIP_CODE],
        arbeitspreis=entry.data[CONF_ARBEITSPREIS],
        environment=entry.data.get(CONF_ENVIRONMENT, ENV_PRODUCTION),
    )
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: OstromConfigEntry) -> bool:
    """Unload Ostrom config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
