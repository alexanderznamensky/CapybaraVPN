"""Sensors for CapybaraVPN."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfInformation, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN
from .entity import CapybaraVPNEntity


def _ms_datetime(value: Any) -> datetime | None:
    try:
        return datetime.fromtimestamp(float(value) / 1000.0, tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


def _iso_datetime(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _last_payment(data: dict) -> dict:
    payments = data.get("payments", {}).get("payments", [])
    if not payments:
        return {}
    return payments[0]


@dataclass(frozen=True, kw_only=True)
class AccountSensorDescription(SensorEntityDescription):
    value_fn: Callable[[dict], Any]


@dataclass(frozen=True, kw_only=True)
class KeySensorDescription(SensorEntityDescription):
    value_fn: Callable[[dict], Any]


ACCOUNT_SENSORS: tuple[AccountSensorDescription, ...] = (
    AccountSensorDescription(
        key="balance",
        name="Баланс",
        icon="mdi:wallet",
        native_unit_of_measurement="RUB",
        value_fn=lambda d: d.get("summary", {}).get("balance"),
    ),
    AccountSensorDescription(
        key="last_payment_amount",
        name="Последний платёж",
        icon="mdi:cash-check",
        native_unit_of_measurement="RUB",
        value_fn=lambda d: _last_payment(d).get("amount"),
    ),
    AccountSensorDescription(
        key="last_payment_date",
        name="Дата последнего платежа",
        icon="mdi:calendar-check",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: _iso_datetime(_last_payment(d).get("created_at")),
    ),
)

KEY_SENSORS: tuple[KeySensorDescription, ...] = (
    KeySensorDescription(
        key="subscription_end",
        name="Действует до",
        icon="mdi:calendar-clock",
        device_class=SensorDeviceClass.TIMESTAMP,
        value_fn=lambda d: _ms_datetime(
            d.get("details", {}).get("expiry_time")
            or d.get("key", {}).get("expiry_time")
        ),
    ),
    KeySensorDescription(
        key="days_left",
        name="Осталось дней",
        icon="mdi:timer-sand",
        native_unit_of_measurement=UnitOfTime.DAYS,
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get("connection", {}).get("expires_in_days"),
    ),
    KeySensorDescription(
        key="tariff",
        name="Тариф",
        icon="mdi:card-account-details-outline",
        value_fn=lambda d: d.get("details", {}).get("tariff_name"),
    ),
    KeySensorDescription(
        key="tariff_price",
        name="Стоимость тарифа",
        icon="mdi:cash",
        native_unit_of_measurement="RUB",
        value_fn=lambda d: d.get("addons", {}).get("total_price_rub"),
    ),
    KeySensorDescription(
        key="used_traffic",
        name="Использовано трафика",
        icon="mdi:chart-line",
        native_unit_of_measurement=UnitOfInformation.GIGABYTES,
        state_class=SensorStateClass.TOTAL_INCREASING,
        value_fn=lambda d: d.get("details", {}).get("used_traffic_gb"),
    ),
    KeySensorDescription(
        key="device_limit",
        name="Лимит устройств",
        icon="mdi:devices",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get("details", {}).get("device_limit"),
    ),
    KeySensorDescription(
        key="connected_devices",
        name="Подключено устройств",
        icon="mdi:devices",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda d: d.get("details", {}).get("connected_devices"),
    ),
    KeySensorDescription(
        key="protocol",
        name="Протокол",
        icon="mdi:shield-key-outline",
        entity_category=EntityCategory.DIAGNOSTIC,
        value_fn=lambda d: d.get("connection", {}).get("protocol"),
    ),
)


class CapybaraAccountSensor(CapybaraVPNEntity, SensorEntity):
    """Account-level sensor."""

    entity_description: AccountSensorDescription

    def __init__(self, coordinator, client_id: str, identity_id: str, description) -> None:
        super().__init__(coordinator, client_id)
        self.entity_description = description
        self._attr_unique_id = f"{identity_id}_{description.key}"

    @property
    def native_value(self):
        return self.entity_description.value_fn(self.coordinator.data)


class CapybaraKeySensor(CapybaraVPNEntity, SensorEntity):
    """Per-subscription sensor."""

    entity_description: KeySensorDescription

    def __init__(self, coordinator, identity_id: str, client_id: str, description) -> None:
        super().__init__(coordinator, client_id)
        self.entity_description = description
        self._attr_unique_id = f"{client_id}_{description.key}"

    @property
    def native_value(self):
        item = self._key_data()
        if not item:
            return None
        return self.entity_description.value_fn(item)



async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    data = hass.data[DOMAIN][entry.entry_id]
    coordinator = data["coordinator"]
    identity_id = str(coordinator.data.get("me", {}).get("id") or entry.unique_id)

    key_items = coordinator.data.get("keys", [])
    if not key_items:
        return

    def get_client_id(item: dict) -> str | None:
        return (
            item.get("details", {}).get("client_id")
            or item.get("key", {}).get("client_id")
        )

    primary_client_id = get_client_id(key_items[0])
    if not primary_client_id:
        return

    # Account-level sensors live on the same single CapybaraVPN device.
    entities = [
        CapybaraAccountSensor(
            coordinator,
            primary_client_id,
            identity_id,
            description,
        )
        for description in ACCOUNT_SENSORS
    ]

    known: set[str] = set()

    def new_key_entities():
        result = []
        for item in coordinator.data.get("keys", []):
            client_id = get_client_id(item)
            if not client_id or client_id in known:
                continue
            known.add(client_id)
            result.extend(
                CapybaraKeySensor(
                    coordinator,
                    identity_id,
                    client_id,
                    description,
                )
                for description in KEY_SENSORS
            )
        return result

    entities.extend(new_key_entities())
    async_add_entities(entities)

    def _discover_new_keys() -> None:
        fresh = new_key_entities()
        if fresh:
            async_add_entities(fresh)

    entry.async_on_unload(coordinator.async_add_listener(_discover_new_keys))
