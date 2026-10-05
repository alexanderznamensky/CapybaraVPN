"""CapybaraVPN integration."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant

from .api import CapybaraVPNClient
from .const import BASE_URL, DOMAIN, PLATFORMS
from .coordinator import CapybaraVPNCoordinator


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up CapybaraVPN from the UI config entry."""
    client = CapybaraVPNClient(
        email=entry.data[CONF_EMAIL],
        password=entry.data[CONF_PASSWORD],
        base_url=BASE_URL,
    )
    coordinator = CapybaraVPNCoordinator(hass, client, entry)

    try:
        await coordinator.async_config_entry_first_refresh()
    except Exception:
        await client.close()
        raise

    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = {
        "client": client,
        "coordinator": coordinator,
    }

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload CapybaraVPN."""
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        data = hass.data[DOMAIN].pop(entry.entry_id)
        await data["client"].close()
    return unloaded
