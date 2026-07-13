"""Support for Gree sensors."""

from __future__ import annotations

# Standard library imports
import logging
from dataclasses import dataclass

# Home Assistant imports
from homeassistant.components.sensor import (
    SensorEntity,
    SensorEntityDescription,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    PERCENTAGE,
    UnitOfTemperature,
)


# Local imports
from .const import DOMAIN
from .entity import GreeEntity, GreeEntityDescription

_LOGGER = logging.getLogger(__name__)


def _eco_shutoff_temp_value(device) -> float | None:
    """Read temperature from the configured Eco Shutoff auxiliary sensor."""
    sensor_id = getattr(device, "_eco_shutoff_sensor", None)
    if not sensor_id:
        return None
    state = device.hass.states.get(sensor_id)
    if state is None or state.state in ("unavailable", "unknown"):
        return None
    try:
        val = float(state.state)
    except (ValueError, TypeError):
        return None
    # Convert to match the climate entity's display unit
    sensor_unit = state.attributes.get("unit_of_measurement", "°C")
    if device.temperature_unit == UnitOfTemperature.CELSIUS:
        if sensor_unit in (UnitOfTemperature.FAHRENHEIT, "°F"):
            val = (val - 32.0) * 5.0 / 9.0
    else:
        if sensor_unit not in (UnitOfTemperature.FAHRENHEIT, "°F"):
            val = val * 9.0 / 5.0 + 32.0
    return round(val, 1)


@dataclass
class GreeSensorEntityDescription(GreeEntityDescription, SensorEntityDescription):
    """Describes Gree Sensor entity."""

    pass


SENSORS: tuple[GreeSensorEntityDescription, ...] = (
    GreeSensorEntityDescription(
        property_key="outside_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=0,
        value_fn=lambda device: device.outside_temperature if device._has_outside_temp_sensor else None,
        available_fn=lambda device: device.available and device._has_outside_temp_sensor,
    ),
    GreeSensorEntityDescription(
        property_key="room_humidity",
        device_class=SensorDeviceClass.HUMIDITY,
        state_class=SensorStateClass.MEASUREMENT,
        native_unit_of_measurement=PERCENTAGE,
        suggested_display_precision=0,
        value_fn=lambda device: device.room_humidity if device._has_room_humidity_sensor else None,
        available_fn=lambda device: device.available and device._has_room_humidity_sensor,
    ),
    # Device state sensors
    GreeSensorEntityDescription(
        property_key="power_state",
        translation_key="power_state",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device._acOptions.get('Pow') if device._acOptions else None,
        available_fn=lambda device: device.available,
    ),
    GreeSensorEntityDescription(
        property_key="device_mode",
        translation_key="device_mode",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device._acOptions.get('Mod') if device._acOptions else None,
        available_fn=lambda device: device.available,
    ),
    GreeSensorEntityDescription(
        property_key="target_temp_raw",
        translation_key="target_temp_raw",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device._acOptions.get('SetTem') if device._acOptions else None,
        available_fn=lambda device: device.available,
    ),
    GreeSensorEntityDescription(
        property_key="fan_speed_raw",
        translation_key="fan_speed_raw",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device._acOptions.get('WdSpd') if device._acOptions else None,
        available_fn=lambda device: device.available,
    ),
    GreeSensorEntityDescription(
        property_key="turbo_mode",
        translation_key="turbo_mode",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device._acOptions.get('Tur') if device._acOptions else None,
        available_fn=lambda device: device.available,
    ),
    GreeSensorEntityDescription(
        property_key="quiet_mode",
        translation_key="quiet_mode",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device._acOptions.get('Quiet') if device._acOptions else None,
        available_fn=lambda device: device.available,
    ),
    GreeSensorEntityDescription(
        property_key="eco_shutoff_temperature",
        translation_key="eco_shutoff_temperature",
        device_class=SensorDeviceClass.TEMPERATURE,
        state_class=SensorStateClass.MEASUREMENT,
        suggested_display_precision=1,
        value_fn=_eco_shutoff_temp_value,
        available_fn=lambda device: bool(getattr(device, "_eco_shutoff_sensor", None)),
    ),
    GreeSensorEntityDescription(
        property_key="power_save_state",
        translation_key="power_save_state",
        state_class=SensorStateClass.MEASUREMENT,
        value_fn=lambda device: device._acOptions.get('SvSt') if device._acOptions else None,
        available_fn=lambda device: device.available,
    ),
)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Gree sensors from a config entry."""
    # Get the device that was created in __init__.py
    entry_data = hass.data[DOMAIN][entry.entry_id]
    device = entry_data["device"]

    sensors = []

    for description in SENSORS:
        if description.exists_fn(description, device):
            sensors.append(GreeSensor(hass, entry, description))
            _LOGGER.debug(f"Added {description.property_key} sensor")

    if sensors:
        async_add_entities(sensors)
        _LOGGER.info(f"Added {len(sensors)} Gree sensors")


class GreeSensor(GreeEntity, SensorEntity):
    """Gree sensor entity."""

    entity_description: GreeSensorEntityDescription

    def __init__(self, hass, entry, description: GreeSensorEntityDescription) -> None:
        """Initialize Gree sensor."""
        super().__init__(hass, entry, description)

        # Set temperature unit for temperature sensors
        if description.device_class == SensorDeviceClass.TEMPERATURE:
            self._attr_native_unit_of_measurement = self._device.temperature_unit

    @property
    def native_value(self):
        """Return the native value of the sensor."""
        return self.entity_description.value_fn(self._device)

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.entity_description.available_fn(self._device)
