"""Support for Gree button entities."""

from __future__ import annotations

# Standard library imports
import logging
from dataclasses import dataclass

# Home Assistant imports
from homeassistant.components.button import (
    ButtonEntity,
    ButtonEntityDescription,
)

# Local imports
from .const import DOMAIN
from .entity import GreeEntity, GreeEntityDescription

_LOGGER = logging.getLogger(__name__)


@dataclass
class GreeButtonEntityDescription(GreeEntityDescription, ButtonEntityDescription):
    """Describes Gree Button entity."""

    press_fn: callable = None


BUTTONS: tuple[GreeButtonEntityDescription, ...] = (
    GreeButtonEntityDescription(
        property_key="clear_manual_override",
        translation_key="clear_manual_override",
        icon="mdi:restore",
        press_fn=lambda device: device.async_resume_normal(),
    ),
)


async def async_setup_entry(hass, entry, async_add_entities):
    """Set up Gree button entities from a config entry."""
    # Get the device that was created in __init__.py
    entry_data = hass.data[DOMAIN][entry.entry_id]
    device = entry_data["device"]

    buttons = []

    for description in BUTTONS:
        if description.exists_fn(description, device):
            buttons.append(GreeButton(hass, entry, description))
            _LOGGER.debug(f"Added {description.property_key} button")

    if buttons:
        async_add_entities(buttons)
        _LOGGER.info(f"Added {len(buttons)} Gree buttons")


class GreeButton(GreeEntity, ButtonEntity):
    """Gree button entity."""

    entity_description: GreeButtonEntityDescription

    def __init__(self, hass, entry, description: GreeButtonEntityDescription) -> None:
        """Initialize Gree button."""
        super().__init__(hass, entry, description)

    async def async_press(self) -> None:
        """Handle the button press."""
        if self.entity_description.press_fn:
            await self.entity_description.press_fn(self._device)
        self.async_write_ha_state()

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.entity_description.available_fn(self._device)
