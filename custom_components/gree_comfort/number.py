"""Support for Gree number entities (e.g., target temperature step)."""

from __future__ import annotations

# Standard library imports
import logging
from collections.abc import Callable
from dataclasses import dataclass

# Home Assistant imports
from homeassistant.components.number import (
    NumberDeviceClass,
    NumberEntityDescription,
    NumberMode,
    RestoreNumber,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import UnitOfTemperature, UnitOfTime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.unit_conversion import TemperatureConverter, TemperatureDeltaConverter

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
        device_class=NumberDeviceClass.TEMPERATURE,
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
        device_class=NumberDeviceClass.TEMPERATURE,
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
        device_class=NumberDeviceClass.TEMPERATURE,
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
        device_class=NumberDeviceClass.TEMPERATURE,
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
        device_class=NumberDeviceClass.TEMPERATURE,
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
        device_class=NumberDeviceClass.TEMPERATURE,
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
        device_class=NumberDeviceClass.TEMPERATURE_DELTA,
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
        device_class=NumberDeviceClass.TEMPERATURE_DELTA,
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


class GreeNumberEntity(GreeEntity, RestoreNumber):
    """Defines a Gree number entity.

    Values are held internally in °C. Temperatures report in the HA unit, rounded to 0.1: HA
    rounds a converted number to the native value's decimal places, so 25.56 °C would show as
    78.01 °F, and it picks no display unit for a delta at all.
    """

    entity_description: GreeNumberEntityDescription

    def __init__(self, hass, entry, description: GreeNumberEntityDescription) -> None:
        self._entry = entry
        self._restored = False
        self._display_unit = hass.config.units.temperature_unit
        self._internal_value = None

        super().__init__(hass, entry, description)

        if self.entity_description.value_fn:
            try:
                self._internal_value = self.entity_description.value_fn(self._device)
            except (AttributeError, KeyError, TypeError):
                pass

    def _is_temperature(self) -> bool:
        return self.entity_description.device_class in (NumberDeviceClass.TEMPERATURE, NumberDeviceClass.TEMPERATURE_DELTA)

    def _from_c(self, value: float) -> float:
        """Convert an internal °C value to the HA unit for display."""
        converter = TemperatureDeltaConverter if self.entity_description.device_class == NumberDeviceClass.TEMPERATURE_DELTA else TemperatureConverter
        return round(float(converter.convert(value, UnitOfTemperature.CELSIUS, self._display_unit)), 1)

    def _to_internal(self, value: float, unit: str | None) -> float:
        """Convert a value in the given unit to the internal °C representation."""
        device_class = self.entity_description.device_class
        if device_class == NumberDeviceClass.TEMPERATURE:
            return round(TemperatureConverter.convert(value, unit or UnitOfTemperature.CELSIUS, UnitOfTemperature.CELSIUS), 2)
        if device_class == NumberDeviceClass.TEMPERATURE_DELTA:
            return round(TemperatureDeltaConverter.convert(value, unit or UnitOfTemperature.CELSIUS, UnitOfTemperature.CELSIUS), 2)
        return value

    @property
    def native_unit_of_measurement(self):
        if self._is_temperature():
            return self._display_unit
        return self.entity_description.native_unit_of_measurement

    @property
    def native_min_value(self):
        value = self.entity_description.native_min_value
        return self._from_c(value) if self._is_temperature() else value

    @property
    def native_max_value(self):
        value = self.entity_description.native_max_value
        return self._from_c(value) if self._is_temperature() else value

    @property
    def native_step(self):
        value = self.entity_description.native_step
        if self.entity_description.device_class == NumberDeviceClass.TEMPERATURE:
            # The unit takes whole °F setpoints, or half °C ones
            return 1.0 if self._display_unit == UnitOfTemperature.FAHRENHEIT else value
        return self._from_c(value) if self._is_temperature() else value

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        if not self.entity_description.restore_state:
            return

        # RestoreNumber data records its unit; older RestoreEntity states fall back to the state's unit attribute
        last_data = await self.async_get_last_number_data()
        if last_data is not None and last_data.native_value is not None:
            value, unit = last_data.native_value, last_data.native_unit_of_measurement
        else:
            last_state = await self.async_get_last_state()
            if last_state is None or last_state.state in ("unknown", "unavailable"):
                return
            try:
                value = float(last_state.state)
            except (ValueError, TypeError):
                return
            unit = last_state.attributes.get("unit_of_measurement")

        try:
            restored_value = self._to_internal(value, unit)
        except (ValueError, TypeError) as err:
            _LOGGER.warning(f"Could not restore {self.entity_id} from {value} {unit}: {err}")
            return

        min_c = self.entity_description.native_min_value
        max_c = self.entity_description.native_max_value
        if not min_c <= restored_value <= max_c:
            _LOGGER.warning(f"Restored {self.entity_id} value {restored_value} outside {min_c}..{max_c}, keeping default")
            return

        if self.entity_description.set_fn:
            self.entity_description.set_fn(self._device, restored_value)
        else:
            setattr(self._device, f"_{self.entity_description.property_key}", restored_value)
        self._internal_value = restored_value
        self._restored = True

    @property
    def native_value(self):
        if self.entity_description.restore_state and self._internal_value is not None:
            value = self._internal_value
        else:
            value = self.entity_description.value_fn(self._device)
        if value is not None and self._is_temperature():
            return self._from_c(value)
        return value

    async def async_set_native_value(self, value: float) -> None:
        """Set a new value, given in the native unit."""
        internal_value = self._to_internal(value, self.native_unit_of_measurement)

        if self.entity_description.set_fn:
            await self.hass.async_add_executor_job(self.entity_description.set_fn, self._device, internal_value)

        # If this is a preset temperature and the preset is currently active, re-apply it
        if self.entity_description.property_key.startswith("preset_"):
            # e.g., "preset_sleep_heat" -> preset="sleep", mode="heat"
            parts = self.entity_description.property_key.split("_")
            if len(parts) >= 3:
                preset_name = parts[1]
                temp_mode = parts[2]

                from homeassistant.components.climate import HVACMode
                if (self._device._preset_mode == preset_name and
                    not self._device._manual_override and
                    ((temp_mode == "heat" and self._device.hvac_mode == HVACMode.HEAT) or
                     (temp_mode == "cool" and self._device.hvac_mode == HVACMode.COOL))):
                    await self._device._apply_preset_temperature()
                    _LOGGER.info(f"Re-applied {preset_name} {temp_mode} temperature after change to {internal_value}°C")

        self._internal_value = internal_value
        self.async_write_ha_state()
