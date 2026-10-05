"""Update coordinator for CapybaraVPN."""

from __future__ import annotations

from datetime import timedelta
import logging

from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import CapybaraVPNAuthError, CapybaraVPNClient, CapybaraVPNError
from .const import CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MINUTES, DOMAIN

_LOGGER = logging.getLogger(__name__)


class CapybaraVPNCoordinator(DataUpdateCoordinator[dict]):
    """Poll CapybaraVPN and share data between entities."""

    def __init__(self, hass, client: CapybaraVPNClient, config_entry) -> None:
        self.client = client
        interval_minutes = int(
            config_entry.options.get(
                CONF_SCAN_INTERVAL,
                config_entry.data.get(
                    CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_MINUTES
                ),
            )
        )
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(minutes=interval_minutes),
            config_entry=config_entry,
        )

    async def _async_update_data(self) -> dict:
        try:
            return await self.client.get_all()
        except CapybaraVPNAuthError as err:
            raise UpdateFailed(f"Authentication failed: {err}") from err
        except CapybaraVPNError as err:
            raise UpdateFailed(f"CapybaraVPN API error: {err}") from err
