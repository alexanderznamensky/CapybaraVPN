"""Binary sensors for CapybaraVPN."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN
from .entity import CapybaraVPNEntity


@dataclass(frozen=True, kw_only=True)
class CapybaraBinaryDescription(BinarySensorEntityDescription):
    value_fn: Callable[[dict], Any]


BINARY_SENSORS: tuple[CapybaraBinaryDescription, ...] = (
    CapybaraBinaryDescription(
        key="online",
        name="Подключение",
        device_class=BinarySensorDeviceClass.CONNECTIVITY,
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get("connection", {}).get("online"),
    ),
    CapybaraBinaryDescription(
        key="frozen",
        name="Подписка заморожена",
        icon="mdi:snowflake",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get("details", {}).get("is_frozen"),
    ),
)


class CapybaraKeyBinarySensor(CapybaraVPNEntity, BinarySensorEntity):
    """Per-subscription binary sensor."""

    entity_description: CapybaraBinaryDescription

    def __init__(self, coordinator, identity_id: str, client_id: str, description) -> None:
        super().__init__(coordinator, client_id)
        self.entity_description = description
        self._attr_unique_id = f"{client_id}_{description.key}"

    @property
    def is_on(self) -> bool | None:
        item = self._key_data()
        if not item:
            return None
        value = self.entity_description.value_fn(item)
        return None if value is None else bool(value)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    identity_id = str(coordinator.data.get("me", {}).get("id") or entry.unique_id)
    known: set[str] = set()

    def new_entities():
        result = []
        for item in coordinator.data.get("keys", []):
            client_id = (
                item.get("details", {}).get("client_id")
                or item.get("key", {}).get("client_id")
            )
            if not client_id or client_id in known:
                continue
            known.add(client_id)
            result.extend(
                CapybaraKeyBinarySensor(
                    coordinator, identity_id, client_id, description
                )
                for description in BINARY_SENSORS
            )
        return result

    async_add_entities(new_entities())

    def _discover_new_keys() -> None:
        fresh = new_entities()
        if fresh:
            async_add_entities(fresh)

    entry.async_on_unload(coordinator.async_add_listener(_discover_new_keys))
