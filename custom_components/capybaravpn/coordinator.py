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
        """Keep previous snapshot on transient failures and flag stale data."""
        old = self.data if isinstance(self.data, dict) else {}
        try:
            fresh = await self.client.get_all()
        except (CapybaraVPNAuthError, CapybaraVPNError) as err:
            if not old or not old.get("keys"):
                raise UpdateFailed(f"CapybaraVPN API error: {err}") from err
            _LOGGER.warning("CapybaraVPN using cached values: %s", err)
            return {**old, "_stale": True, "_errors": [str(err)]}

        result = {**old, **fresh}
        errors = list(fresh.get("_errors", []))
        # API may omit the keys list when a subscription is suspended.
        # Preserve registered entities rather than removing their data.
        if "keys" not in fresh or (not fresh["keys"] and old.get("keys")):
            result["keys"] = old.get("keys", [])
            if old.get("keys"):
                errors.append("Subscription list missing/empty; previous list retained")
        else:
            old_keys = {
                str(x.get("key", {}).get("client_id")): x
                for x in old.get("keys", [])
            }
            merged = []
            for item in fresh["keys"]:
                cid = str(item.get("key", {}).get("client_id"))
                merged.append({**old_keys.get(cid, {}), **item})
            result["keys"] = merged

        result["_errors"] = errors
        result["_stale"] = bool(errors)
        return result
