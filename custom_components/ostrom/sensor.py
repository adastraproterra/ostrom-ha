"""Sensor platform for Ostrom integration."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    CURRENCY_EURO,
    UnitOfEnergy,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import OstromCoordinator

_LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True)
class OstromSensorEntityDescription(SensorEntityDescription):
    """Describe an Ostrom sensor."""

    data_key: str = ""
    extra_attrs_key: str | None = None


SENSOR_DESCRIPTIONS: tuple[OstromSensorEntityDescription, ...] = (
    OstromSensorEntityDescription(
        key="arbeitspreis",
        name="Arbeitspreis",
        data_key="arbeitspreis",
        native_unit_of_measurement="ct/kWh",
        device_class=None,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:currency-eur",
    ),
    OstromSensorEntityDescription(
        key="current_price",
        name="Aktueller Strompreis",
        data_key="current_price_eur",
        native_unit_of_measurement=f"{CURRENCY_EURO}/kWh",
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.MEASUREMENT,
        icon="mdi:lightning-bolt",
        extra_attrs_key="forecast",
    ),
    OstromSensorEntityDescription(
        key="monthly_consumption",
        name="Verbrauch diesen Monat",
        data_key="monthly_kwh",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:meter-electric",
    ),
    OstromSensorEntityDescription(
        key="daily_consumption",
        name="Verbrauch heute",
        data_key="daily_kwh",
        native_unit_of_measurement=UnitOfEnergy.KILO_WATT_HOUR,
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:meter-electric-outline",
    ),
    OstromSensorEntityDescription(
        key="total_cost",
        name="Kosten diesen Monat",
        data_key="total_cost",
        native_unit_of_measurement=CURRENCY_EURO,
        device_class=SensorDeviceClass.MONETARY,
        state_class=SensorStateClass.TOTAL_INCREASING,
        icon="mdi:cash",
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Ostrom sensors from config entry."""
    coordinator: OstromCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        OstromSensor(coordinator, description, entry)
        for description in SENSOR_DESCRIPTIONS
    )


class OstromSensor(CoordinatorEntity[OstromCoordinator], SensorEntity):
    """Representation of an Ostrom sensor."""

    entity_description: OstromSensorEntityDescription

    def __init__(
        self,
        coordinator: OstromCoordinator,
        description: OstromSensorEntityDescription,
        entry: ConfigEntry,
    ) -> None:
        """Initialize sensor."""
        super().__init__(coordinator)
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_name = description.name
        self._attr_device_info = {
            "identifiers": {(DOMAIN, entry.entry_id)},
            "name": "Ostrom",
            "manufacturer": "Ostrom",
            "model": "Energie API",
        }

    @property
    def native_value(self) -> Any:
        """Return sensor value."""
        if self.coordinator.data is None:
            return None
        return self.coordinator.data.get(self.entity_description.data_key)

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return extra state attributes (e.g. forecast)."""
        if (
            self.entity_description.extra_attrs_key is None
            or self.coordinator.data is None
        ):
            return None
        value = self.coordinator.data.get(self.entity_description.extra_attrs_key)
        if value is None:
            return None
        return {"preisprognose_24h": value}
      
