"""Support for Gree number entities (e.g., target temperature step)."""

from __future__ import annotations

# Standard library imports
import logging
from collections.abc import Callable
from dataclasses import dataclass

# Home Assistant imports
from homeassistant.components.number import (
    NumberEntity,
    NumberEntityDescription,
    NumberMode,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

# Local imports
from .const import DEFAULT_TARGET_TEMP_STEP, MIN_TEMP_C, MAX_TEMP_C
from .entity import GreeEntity, GreeEntityDescription

_LOGGER = logging.getLogger(__name__)


@dataclass
class GreeNumberEntityDescription(GreeEntityDescription, NumberEntityDescription):
    set_fn: Callable[[object, float], None] = None
    restore_state: bool = False


NUMBERS: tuple[GreeNumberEntityDescription, ...] = (
    GreeNumberEntityDescription(
        property_key="target_temp_step",
        icon="mdi:arrow-expand-vertical",
        native_min_value=0.1,
        native_max_value=5.0,
        native_step=0.1,
        mode=NumberMode.SLIDER,
        value_fn=lambda device: getattr(device, "_target_temperature_step", DEFAULT_TARGET_TEMP_STEP),
        set_fn=lambda device, value: setattr(device, "_target_temperature_step", value),
        entity_category=EntityCategory.CONFIG,
        restore_state=True,
    ),
    # Preset temperature number entities
    GreeNumberEntityDescription(
        property_key="preset_home_heat",
        translation_key="preset_home_heat",
        icon="mdi:home-thermometer",
        native_min_value=MIN_TEMP_C,
        native_max_value=MAX_TEMP_C,
        native_step=0.5,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        mode=NumberMode.BOX,
        value_fn=lambda device: device._preset_temps.get("home", {}).get("heat", 20),
        set_fn=lambda device, value: device._preset_temps.get("home", {}).update({"heat": value}),
        entity_category=EntityCategory.CONFIG,
        restore_state=True,
    ),
    GreeNumberEntityDescription(
        property_key="preset_home_cool",
        translation_key="preset_home_cool",
        icon="mdi:home-thermometer-outline",
        native_min_value=MIN_TEMP_C,
        native_max_value=MAX_TEMP_C,
        native_step=0.5,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        mode=NumberMode.BOX,
        value_fn=lambda device: device._preset_temps.get("home", {}).get("cool", 24),
        set_fn=lambda device, value: device._preset_temps.get("home", {}).update({"cool": value}),
        entity_category=EntityCategory.CONFIG,
        restore_state=True,
    ),
    GreeNumberEntityDescription(
        property_key="preset_sleep_heat",
        translation_key="preset_sleep_heat",
        icon="mdi:sleep",
        native_min_value=MIN_TEMP_C,
        native_max_value=MAX_TEMP_C,
        native_step=0.5,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        mode=NumberMode.BOX,
        value_fn=lambda device: device._preset_temps.get("sleep", {}).get("heat", 17),
        set_fn=lambda device, value: device._preset_temps.get("sleep", {}).update({"heat": value}),
        entity_category=EntityCategory.CONFIG,
        restore_state=True,
    ),
    GreeNumberEntityDescription(
        property_key="preset_sleep_cool",
        translation_key="preset_sleep_cool",
        icon="mdi:sleep",
        native_min_value=MIN_TEMP_C,
        native_max_value=MAX_TEMP_C,
        native_step=0.5,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        mode=NumberMode.BOX,
        value_fn=lambda device: device._preset_temps.get("sleep", {}).get("cool", 26),
        set_fn=lambda device, value: device._preset_temps.get("sleep", {}).update({"cool": value}),
        entity_category=EntityCategory.CONFIG,
        restore_state=True,
    ),
    GreeNumberEntityDescription(
        property_key="preset_away_heat",
        translation_key="preset_away_heat",
        icon="mdi:home-export-outline",
        native_min_value=MIN_TEMP_C,
        native_max_value=MAX_TEMP_C,
        native_step=0.5,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        mode=NumberMode.BOX,
        value_fn=lambda device: device._preset_temps.get("away", {}).get("heat", 15),
        set_fn=lambda device, value: device._preset_temps.get("away", {}).update({"heat": value}),
        entity_category=EntityCategory.CONFIG,
        restore_state=True,
    ),
    GreeNumberEntityDescription(
        property_key="preset_away_cool",
        translation_key="preset_away_cool",
        icon="mdi:home-export-outline",
        native_min_value=MIN_TEMP_C,
        native_max_value=MAX_TEMP_C,
        native_step=0.5,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        mode=NumberMode.BOX,
        value_fn=lambda device: device._preset_temps.get("away", {}).get("cool", 28),
        set_fn=lambda device, value: device._preset_temps.get("away", {}).update({"cool": value}),
        entity_category=EntityCategory.CONFIG,
        restore_state=True,
    ),
    GreeNumberEntityDescription(
        property_key="eco_shutoff_satisfied_margin",
        translation_key="eco_shutoff_satisfied_margin",
        icon="mdi:thermometer-chevron-up",
        native_min_value=1.0,
        native_max_value=5.0,
        native_step=0.5,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        mode=NumberMode.SLIDER,
        value_fn=lambda device: getattr(device, "_eco_shutoff_satisfied_margin", 1.5),
        set_fn=lambda device, value: setattr(device, "_eco_shutoff_satisfied_margin", value),
        entity_category=EntityCategory.CONFIG,
        restore_state=True,
    ),
    GreeNumberEntityDescription(
        property_key="eco_shutoff_reengage_delta",
        translation_key="eco_shutoff_reengage_delta",
        icon="mdi:thermometer-chevron-down",
        native_min_value=0.3,
        native_max_value=3.0,
        native_step=0.1,
        native_unit_of_measurement=UnitOfTemperature.CELSIUS,
        mode=NumberMode.SLIDER,
        value_fn=lambda device: getattr(device, "_eco_shutoff_reengage_delta", 0.5),
        set_fn=lambda device, value: setattr(device, "_eco_shutoff_reengage_delta", value),
        entity_category=EntityCategory.CONFIG,
        restore_state=True,
    ),
    GreeNumberEntityDescription(
        property_key="eco_shutoff_trend_window_minutes",
        translation_key="eco_shutoff_trend_window_minutes",
        icon="mdi:chart-line",
        native_min_value=3,
        native_max_value=15,
        native_step=1,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        mode=NumberMode.SLIDER,
        value_fn=lambda device: getattr(device, "_eco_shutoff_trend_window_minutes", 5),
        set_fn=lambda device, value: setattr(device, "_eco_shutoff_trend_window_minutes", value),
        entity_category=EntityCategory.CONFIG,
        restore_state=True,
    ),
    GreeNumberEntityDescription(
        property_key="stht_smart_threshold_minutes",
        translation_key="stht_smart_threshold_minutes",
        icon="mdi:timer-outline",
        native_min_value=30,
        native_max_value=240,
        native_step=30,
        native_unit_of_measurement=UnitOfTime.MINUTES,
        mode=NumberMode.SLIDER,
        value_fn=lambda device: getattr(device, "_stht_smart_threshold_minutes", 60),
        set_fn=lambda device, value: setattr(device, "_stht_smart_threshold_minutes", value),
        entity_category=EntityCategory.CONFIG,
        restore_state=True,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Gree number entities based on a config entry."""
    async_add_entities(GreeNumberEntity(hass, entry, description) for description in NUMBERS)


class GreeNumberEntity(GreeEntity, NumberEntity, RestoreEntity):
    """Defines a Gree number entity."""

    entity_description: GreeNumberEntityDescription

    def __init__(self, hass, entry, description: GreeNumberEntityDescription) -> None:
        # Store entry reference for later use
        self._entry = entry
        self._restored = False
        self._use_fahrenheit = hass.config.units.temperature_unit == UnitOfTemperature.FAHRENHEIT

        super().__init__(hass, entry, description)

        # Initialize with Celsius value from device (not converted)
        if self.entity_description.value_fn:
            try:
                self._attr_native_value = self.entity_description.value_fn(self._device)
            except (AttributeError, KeyError, TypeError):
                pass

    @property
    def native_unit_of_measurement(self):
        """Return the unit based on user preference for temperature entities."""
        if self.entity_description.native_unit_of_measurement == UnitOfTemperature.CELSIUS:
            return UnitOfTemperature.FAHRENHEIT if self._use_fahrenheit else UnitOfTemperature.CELSIUS
        return self.entity_description.native_unit_of_measurement

    _DELTA_TEMP_KEYS = frozenset({
        "eco_shutoff_satisfied_margin",
        "eco_shutoff_reengage_delta",
    })

    def _is_delta_temp(self):
        return self.entity_description.property_key in self._DELTA_TEMP_KEYS

    @property
    def native_min_value(self):
        """Return min value, converted if needed."""
        min_val = self.entity_description.native_min_value
        if self._use_fahrenheit and self.entity_description.native_unit_of_measurement == UnitOfTemperature.CELSIUS:
            if self._is_delta_temp():
                return round(min_val * 9.0 / 5.0, 1)
            else:
                return round(min_val * 9.0 / 5.0 + 32.0, 1)
        return min_val

    @property
    def native_max_value(self):
        """Return max value, converted if needed."""
        max_val = self.entity_description.native_max_value
        if self._use_fahrenheit and self.entity_description.native_unit_of_measurement == UnitOfTemperature.CELSIUS:
            if self._is_delta_temp():
                return round(max_val * 9.0 / 5.0, 1)
            else:
                return round(max_val * 9.0 / 5.0 + 32.0, 1)
        return max_val

    @property
    def native_step(self):
        """Return step value, converted if needed."""
        step = self.entity_description.native_step
        if self._use_fahrenheit and self.entity_description.native_unit_of_measurement == UnitOfTemperature.CELSIUS:
            # Step is always a delta
            return round(step * 9.0 / 5.0, 1)
        return step

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        if self.entity_description.restore_state:
            last_state = await self.async_get_last_state()
            if last_state is not None and last_state.state not in ["unknown", "unavailable"]:
                try:
                    restored_value = float(last_state.state)

                    # Migrate old Fahrenheit values to Celsius (stored values > 30 are assumed Fahrenheit)
                    # Compare against raw Celsius max from entity_description, not the property
                    if (self.entity_description.native_unit_of_measurement == UnitOfTemperature.CELSIUS and
                        restored_value > MAX_TEMP_C):
                        restored_value = (restored_value - 32.0) * 5.0 / 9.0

                    # Validate against raw Celsius values from entity_description
                    min_c = self.entity_description.native_min_value
                    max_c = self.entity_description.native_max_value
                    if min_c <= restored_value <= max_c:
                        # Use set_fn to properly update the device state
                        if self.entity_description.set_fn:
                            self.entity_description.set_fn(self._device, restored_value)
                        else:
                            setattr(self._device, f"_{self.entity_description.property_key}", restored_value)
                        self._attr_native_value = restored_value
                        self._restored = True
                except (ValueError, TypeError):
                    pass

    @property
    def native_value(self):
        """Return the current value, converted if needed."""
        if self.entity_description.restore_state:
            value = getattr(self, "_attr_native_value", self.entity_description.value_fn(self._device))
        else:
            value = self.entity_description.value_fn(self._device)

        # Convert from stored Celsius to Fahrenheit if needed
        if value is not None and self._use_fahrenheit and self.entity_description.native_unit_of_measurement == UnitOfTemperature.CELSIUS:
            if self._is_delta_temp():
                return round(value * 9.0 / 5.0, 1)
            else:
                return round(value * 9.0 / 5.0 + 32.0, 1)
        return value

    async def async_set_native_value(self, value: float) -> None:
        """Set new value, converting from display unit to Celsius if needed."""
        # Convert from Fahrenheit to Celsius if needed
        celsius_value = value
        if self._use_fahrenheit and self.entity_description.native_unit_of_measurement == UnitOfTemperature.CELSIUS:
            if self._is_delta_temp():
                celsius_value = value * 5.0 / 9.0
            else:
                celsius_value = (value - 32.0) * 5.0 / 9.0

        if self.entity_description.set_fn:
            await self.hass.async_add_executor_job(self.entity_description.set_fn, self._device, celsius_value)

        # If this is a preset temperature and the preset is currently active, re-apply it
        if self.entity_description.property_key.startswith("preset_"):
            # Extract preset name and mode (heat/cool) from property_key
            # e.g., "preset_sleep_heat" -> preset="sleep", mode="heat"
            parts = self.entity_description.property_key.split("_")
            if len(parts) >= 3:
                preset_name = parts[1]  # "home", "sleep", or "away"
                temp_mode = parts[2]    # "heat" or "cool"

                # Check if this preset is currently active and matches the mode
                from homeassistant.components.climate import HVACMode
                if (self._device._preset_mode == preset_name and
                    not self._device._manual_override and
                    ((temp_mode == "heat" and self._device.hvac_mode == HVACMode.HEAT) or
                     (temp_mode == "cool" and self._device.hvac_mode == HVACMode.COOL))):
                    # Re-apply the preset temperature immediately
                    await self._device._apply_preset_temperature()
                    _LOGGER.info(f"Re-applied {preset_name} {temp_mode} temperature after change to {celsius_value}°C")

        if self.entity_description.restore_state:
            # Store the value internally in Celsius
            self._attr_native_value = celsius_value
        self.async_write_ha_state()
