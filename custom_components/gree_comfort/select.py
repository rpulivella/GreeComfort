"""Support for Gree select entities (e.g., Eco Shutoff temperature sensor selection)."""

from __future__ import annotations

# Standard library imports
import logging
from collections.abc import Callable
from dataclasses import dataclass

# Home Assistant imports
from homeassistant.components.select import (
    SelectEntity,
    SelectEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers import entity_registry as er

# Local imports
from .entity import GreeEntity, GreeEntityDescription
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


@dataclass
class GreeSelectEntityDescription(GreeEntityDescription, SelectEntityDescription):
    """Describes Gree select entity."""

    set_fn: Callable[[object, str], None] = None
    restore_state: bool = False
    options_fn: Callable[[object, str | None], list[str]] = None


def get_temperature_sensor_options(hass: HomeAssistant, entry_id: str | None = None) -> list[str]:
    """Get list of available temperature sensor entities, excluding this device's own sensors."""
    options = ["None"]

    # Build exclusion set: this device's own sensor entities must not be selectable
    # (the built-in AC sensors go dark when the unit is off, defeating the whole point).
    own_entity_ids: set[str] = set()
    if entry_id:
        registry = er.async_get(hass)
        own_entity_ids = {
            e.entity_id
            for e in registry.entities.get_entries_for_config_entry_id(entry_id)
        }

    for state in hass.states.async_all():
        if not state.entity_id.startswith("sensor."):
            continue
        if state.entity_id in own_entity_ids:
            continue
        if state.attributes.get("device_class") == "temperature":
            options.append(state.entity_id)
        elif state.attributes.get("unit_of_measurement") in ["°C", "°F", "K"]:
            options.append(state.entity_id)

    return options


SELECTS: tuple[GreeSelectEntityDescription, ...] = (
    GreeSelectEntityDescription(
        property_key="eco_shutoff_sensor",
        icon="mdi:thermometer-lines",
        options=[],  # Will be populated dynamically
        value_fn=lambda device: getattr(device, "_eco_shutoff_sensor", None) or "None",
        set_fn=lambda device, value: setattr(device, "_eco_shutoff_sensor", None if value == "None" else value),
        entity_category=EntityCategory.CONFIG,
        restore_state=True,
        options_fn=lambda hass, entry_id=None: get_temperature_sensor_options(hass, entry_id),
    ),
    GreeSelectEntityDescription(
        property_key="preset_mode",
        icon="mdi:home-thermometer",
        options=["home", "sleep", "away", "off"],  # User-selectable presets only
        value_fn=lambda device: device._preset_mode if device._preset_mode != "none" else "home",
        set_fn=None,  # Handled by async_select_option override
        entity_category=None,  # Main control, not config
        restore_state=False,  # Sync from climate entity instead
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Gree select entities based on a config entry."""
    async_add_entities(GreeSelectEntity(hass, entry, description) for description in SELECTS)


class GreeSelectEntity(GreeEntity, SelectEntity, RestoreEntity):
    """Defines a Gree select entity."""

    entity_description: GreeSelectEntityDescription

    def __init__(self, hass: HomeAssistant, entry, description: GreeSelectEntityDescription) -> None:
        super().__init__(hass, entry, description)
        self._hass = hass
        self._entry_id = entry.entry_id
        # Initialize with no Eco Shutoff sensor configured
        self._device._eco_shutoff_sensor = None
        # Set up options dynamically
        if description.options_fn:
            self._attr_options = description.options_fn(hass, self._entry_id)
        else:
            self._attr_options = description.options or ["None"]

    async def async_added_to_hass(self) -> None:
        """Restore state when entity is added to hass."""
        await super().async_added_to_hass()

        # Refresh options when entity is added
        if self.entity_description.options_fn:
            self._attr_options = self.entity_description.options_fn(self._hass, self._entry_id)

        # Restore the last selected state if available
        if self.entity_description.restore_state:
            restored = await self.async_get_last_state()
            if restored and self.entity_description.set_fn:
                self.entity_description.set_fn(self._device, restored.state)
                _LOGGER.debug("Restored %s state: %s", self.entity_id, restored.state)

        # Set up dispatcher listener for preset mode updates from climate entity
        if self.entity_description.property_key == "preset_mode":
            signal = f"{DOMAIN}_{self._device._mac_addr}_preset_mode_update"
            self.async_on_remove(
                async_dispatcher_connect(self.hass, signal, self._handle_preset_update)
            )
            _LOGGER.debug("Set up preset mode dispatcher listener: %s", signal)

    @callback
    def _handle_preset_update(self, preset_mode: str):
        """Handle preset mode updates from climate entity."""
        # Only update if preset is a user-selectable option
        if preset_mode in self._attr_options:
            _LOGGER.debug("Preset mode updated via dispatcher: %s", preset_mode)
            self.async_write_ha_state()
        elif preset_mode == "none":
            # Climate is in "none" preset, but we show the last valid preset
            # No need to update, value_fn handles this
            pass

    @property
    def current_option(self) -> str:
        """Return the current selected option."""
        if self.entity_description.value_fn:
            value = self.entity_description.value_fn(self._device)
            return value or "None"
        return "None"

    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        if option not in self._attr_options:
            _LOGGER.error("Option %s not available in %s", option, self._attr_options)
            return

        # Handle preset mode selection by calling climate entity
        if self.entity_description.property_key == "preset_mode":
            await self._device.async_set_preset_mode(option)
            _LOGGER.info("Set preset mode via select entity: %s", option)
        # Handle other select entities with set_fn
        elif self.entity_description.set_fn:
            self.entity_description.set_fn(self._device, option)
            self.async_write_ha_state()
            _LOGGER.info("Selected %s: %s", self.entity_description.property_key, option)

    async def async_update(self) -> None:
        """Update the entity."""
        # Refresh available temperature sensors periodically
        if self.entity_description.options_fn:
            new_options = self.entity_description.options_fn(self._hass, self._entry_id)
            if new_options != self._attr_options:
                self._attr_options = new_options
                _LOGGER.debug("Updated temperature sensor options: %s", self._attr_options)

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return True
