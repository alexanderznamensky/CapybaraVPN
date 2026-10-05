"""Base entity classes for CapybaraVPN."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


class CapybaraVPNEntity(CoordinatorEntity):
    """Base entity."""

    _attr_has_entity_name = True

    def __init__(self, coordinator, identity_id: str, client_id: str | None = None) -> None:
        super().__init__(coordinator)
        self.identity_id = identity_id
        self.client_id = client_id

    def _key_data(self) -> dict | None:
        if self.client_id is None:
            return None
        for item in self.coordinator.data.get("keys", []):
            cid = (
                item.get("details", {}).get("client_id")
                or item.get("key", {}).get("client_id")
            )
            if cid == self.client_id:
                return item
        return None

    @property
    def available(self) -> bool:
        if not self.coordinator.last_update_success:
            return False
        if self.client_id is None:
            return True
        return self._key_data() is not None

    @property
    def device_info(self) -> DeviceInfo:
        if self.client_id is None:
            return DeviceInfo(
                identifiers={(DOMAIN, self.identity_id)},
                name="CapybaraVPN",
                manufacturer="CapybaraVPN",
                model="Account",
                configuration_url="https://capybaravpn.app/dashboard",
            )

        item = self._key_data() or {}
        details = item.get("details", {})
        tariff_name = details.get("tariff_name") or "VPN subscription"
        short_id = self.client_id[:8]

        return DeviceInfo(
            identifiers={(DOMAIN, self.client_id)},
            name=f"CapybaraVPN {short_id}",
            manufacturer="CapybaraVPN",
            model=tariff_name,
            via_device=(DOMAIN, self.identity_id),
            configuration_url="https://capybaravpn.app/dashboard",
        )
