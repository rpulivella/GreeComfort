"""Support for Gree binary sensors."""

from __future__ import annotations

# Standard library imports
import logging
from dataclasses import dataclass

# Home Assistant imports
from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
    BinarySensorDeviceClass,
)
from homeassistant.helpers.dispatcher import async_dispatcher_connect

# Local imports
from .const import DOMAIN
from .entity import GreeEntity, GreeEntityDescription

_LOGGER = logging.getLogger(__name__)


@dataclass
class GreeBinarySensorEntityDescription(GreeEntityDescription, BinarySensorEntityDescription):
    """Describes Gree Binary Sensor entity."""

    pass


BINARY_SENSORS: tuple[GreeBinarySensorEntityDescription, ...] = (
    GreeBinarySensorEntityDescription(
        property_key="manual_override",
        translation_key="manual_override",
        value_fn=lambda device: device._manual_override,
        available_fn=lambda device: device.available,
    ),
)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Gree binary sensors from a config entry."""
    # Get the device that was created in __init__.py
    entry_data = hass.data[DOMAIN][entry.entry_id]
    device = entry_data["device"]

    binary_sensors = []

    for description in BINARY_SENSORS:
        if description.exists_fn(description, device):
            binary_sensors.append(GreeBinarySensor(hass, entry, description))
            _LOGGER.debug(f"Added {description.property_key} binary sensor")

    if binary_sensors:
        async_add_entities(binary_sensors)
        _LOGGER.info(f"Added {len(binary_sensors)} Gree binary sensors")


class GreeBinarySensor(GreeEntity, BinarySensorEntity):
    """Gree binary sensor entity."""

    entity_description: GreeBinarySensorEntityDescription

    def __init__(self, hass, entry, description: GreeBinarySensorEntityDescription) -> None:
        """Initialize Gree binary sensor."""
        super().__init__(hass, entry, description)

    async def async_added_to_hass(self) -> None:
        """Run when entity about to be added to hass."""
        await super().async_added_to_hass()

        # Listen for manual override updates from the climate entity
        if self.entity_description.property_key == "manual_override":
            signal = f"{DOMAIN}_{self._device._mac_addr}_manual_override_update"

            async def handle_update(value):
                """Handle manual override update."""
                self.async_write_ha_state()

            self.async_on_remove(
                async_dispatcher_connect(self.hass, signal, handle_update)
            )

    @property
    def is_on(self):
        """Return true if the binary sensor is on."""
        return self.entity_description.value_fn(self._device)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.entity_description.available_fn(self._device)
