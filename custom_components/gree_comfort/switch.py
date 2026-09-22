"""Support for Gree switches."""

from __future__ import annotations

# Standard library imports
import logging
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

# Home Assistant imports
from homeassistant.components.climate import HVACMode
from homeassistant.components.switch import (
    SwitchEntity,
    SwitchEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import issue_registry as ir
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

# Local imports
from .const import DOMAIN
from .entity import GreeEntity, GreeEntityDescription

_LOGGER = logging.getLogger(__name__)


@dataclass
class GreeSwitchEntityDescription(GreeEntityDescription, SwitchEntityDescription):
    """Describes Gree Switch entity."""

    set_fn: Callable[[object, bool], None] = None
    restore_state: bool = False
    """Whether to restore the state of the switch on startup."""


async def _set_xfan(device, value: bool) -> None:
    await device.SyncState({"Blo": 1 if value else 0})


async def _set_lights(device, value: bool) -> None:
    await device.SyncState({"Lig": 1 if value else 0})


async def _set_health(device, value: bool) -> None:
    await device.SyncState({"Health": 1 if value else 0})


async def _set_powersave(device, value: bool) -> None:
    await device.SyncState({"SvSt": 1 if value else 0})


async def _set_eightdegheat(device, value: bool) -> None:
    await device.SyncState({"StHt": 1 if value else 0})


async def _set_sleep(device, value: bool) -> None:
    await device.SyncState({"SwhSlp": 1 if value else 0, "SlpMod": 1 if value else 0})


async def _set_air(device, value: bool) -> None:
    await device.SyncState({"Air": 1 if value else 0})


async def _set_anti_direct_blow(device, value: bool) -> None:
    await device.SyncState({"AntiDirectBlow": 1 if value else 0})


async def _set_light_sensor(device, value: bool) -> None:
    if value:
        await device.SyncState({"Lig": 1, "LigSen": 0})
    else:
        await device.SyncState({"LigSen": 1})


async def _set_auto_xfan(device, value: bool) -> None:
    device._auto_xfan = value


async def _set_auto_light(device, value: bool) -> None:
    device._auto_light = value


async def _set_beeper(device, value: bool) -> None:
    device._beeper_enabled = value


async def _set_stht_smart(device, value: bool) -> None:
    device._stht_smart_enabled = value
    if not value and getattr(device, "_stht_smart_active", False):
        # Feature disabled while active, deactivate StHt immediately
        device._stht_smart_active = False
        device._preset_active_since = None
        await device.SyncState({"StHt": 0})


async def _set_schedule_auto_release(device, value: bool) -> None:
    device._schedule_auto_release = value


async def _set_eco_shutoff_enabled(device, value: bool) -> None:
    device._eco_shutoff_enabled = value
    if not value and getattr(device, "_eco_shutoff_active", False):
        # Feature disabled while holding unit off, restore power and persist so the
        # Store no longer carries eco_shutoff_active: true across reloads.
        device._eco_shutoff_active = False
        await device.SyncState({"Pow": 1})
        await device._save_persistent_state()
        signal = f"{DOMAIN}_{device._mac_addr}_eco_shutoff_update"
        async_dispatcher_send(device.hass, signal, False)


SWITCHES: tuple[GreeSwitchEntityDescription, ...] = (
    GreeSwitchEntityDescription(
        property_key="xfan",
        icon="mdi:fan",
        value_fn=lambda device: device._acOptions.get("Blo") == 1,
        set_fn=_set_xfan,
    ),
    GreeSwitchEntityDescription(
        property_key="lights",
        icon="mdi:lightbulb",
        value_fn=lambda device: device._acOptions.get("Lig") == 1,
        set_fn=_set_lights,
    ),
    GreeSwitchEntityDescription(
        property_key="health",
        icon="mdi:shield-check",
        value_fn=lambda device: device._acOptions.get("Health") == 1,
        set_fn=_set_health,
    ),
    GreeSwitchEntityDescription(
        property_key="powersave",
        icon="mdi:leaf",
        value_fn=lambda device: device._acOptions.get("SvSt") == 1,
        set_fn=_set_powersave,
        exists_fn=lambda description, device: HVACMode.COOL in device._hvac_modes,
        available_fn=lambda device: device._hvac_mode == HVACMode.COOL,
    ),
    GreeSwitchEntityDescription(
        property_key="eightdegheat",
        icon="mdi:thermometer-low",
        value_fn=lambda device: device._acOptions.get("StHt") == 1,
        set_fn=_set_eightdegheat,
        exists_fn=lambda description, device: HVACMode.HEAT in device._hvac_modes,
        available_fn=lambda device: device._hvac_mode == HVACMode.HEAT,
    ),
    GreeSwitchEntityDescription(
        property_key="sleep",
        icon="mdi:sleep",
        value_fn=lambda device: device._acOptions.get("SwhSlp") == 1 and device._acOptions.get("SlpMod") == 1,
        set_fn=_set_sleep,
        available_fn=lambda device: device._hvac_mode in (HVACMode.COOL, HVACMode.HEAT),
    ),
    GreeSwitchEntityDescription(
        property_key="air",
        icon="mdi:air-filter",
        value_fn=lambda device: device._acOptions.get("Air") == 1,
        set_fn=_set_air,
    ),
    GreeSwitchEntityDescription(
        property_key="anti_direct_blow",
        icon="mdi:weather-windy",
        value_fn=lambda device: device._acOptions.get("AntiDirectBlow") == 1,
        set_fn=_set_anti_direct_blow,
        available_fn=lambda device: getattr(device, "_has_anti_direct_blow", False),
    ),
    GreeSwitchEntityDescription(
        property_key="light_sensor",
        icon="mdi:lightbulb-on",
        value_fn=lambda device: device._acOptions.get("LigSen") == 0,  # LigSen=0 means sensor is active
        set_fn=_set_light_sensor,
        available_fn=lambda device: getattr(device, "_has_light_sensor", False),
    ),
    # These entities are not kept in the climate device
    GreeSwitchEntityDescription(
        property_key="auto_xfan",
        icon="mdi:fan-auto",
        value_fn=lambda device: getattr(device, "_auto_xfan", False),
        set_fn=_set_auto_xfan,
        restore_state=True,
        entity_category=EntityCategory.CONFIG,
    ),
    GreeSwitchEntityDescription(
        property_key="auto_light",
        icon="mdi:lightbulb-auto",
        value_fn=lambda device: getattr(device, "_auto_light", False),
        set_fn=_set_auto_light,
        restore_state=True,
        entity_category=EntityCategory.CONFIG,
    ),
    GreeSwitchEntityDescription(
        property_key="beeper",
        icon="mdi:volume-high",
        value_fn=lambda device: getattr(device, "_beeper_enabled", True),
        set_fn=_set_beeper,
        restore_state=True,
    ),
    GreeSwitchEntityDescription(
        property_key="stht_smart",
        translation_key="stht_smart",
        icon="mdi:thermometer-alert",
        value_fn=lambda device: getattr(device, "_stht_smart_enabled", True),
        set_fn=_set_stht_smart,
        restore_state=True,
        entity_category=EntityCategory.CONFIG,
    ),
    GreeSwitchEntityDescription(
        property_key="schedule_auto_release",
        translation_key="schedule_auto_release",
        icon="mdi:calendar-clock",
        value_fn=lambda device: getattr(device, "_schedule_auto_release", False),
        set_fn=_set_schedule_auto_release,
        restore_state=True,
        entity_category=EntityCategory.CONFIG,
    ),
    GreeSwitchEntityDescription(
        property_key="eco_shutoff_enabled",
        translation_key="eco_shutoff_enabled",
        icon="mdi:power-sleep",
        value_fn=lambda device: getattr(device, "_eco_shutoff_enabled", False),
        set_fn=_set_eco_shutoff_enabled,
        restore_state=True,
        entity_category=EntityCategory.CONFIG,
        available_fn=lambda device: bool(getattr(device, "_eco_shutoff_sensor", None)),
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Gree switch based on a config entry."""
    async_add_entities(GreeSwitchEntity(hass, entry, description) for description in SWITCHES)


class GreeSwitchEntity(GreeEntity, SwitchEntity, RestoreEntity):
    """Defines a Gree Switch entity."""

    entity_description: GreeSwitchEntityDescription

    def __init__(
        self,
        hass,
        entry,
        description: GreeSwitchEntityDescription,
    ) -> None:
        super().__init__(hass, entry, description)
        if description.restore_state and description.value_fn:
            self._attr_is_on = bool(description.value_fn(self._device))
        else:
            self._attr_is_on = bool(self.native_value)
        self._restored = False

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        # Restore state if applicable
        if self.entity_description.restore_state:
            last_state = await self.async_get_last_state()
            if last_state is not None and last_state.state in ("on", "off"):
                value = last_state.state == "on"
                await self.entity_description.set_fn(self._device, value)
                self._attr_is_on = value
                self._restored = True
                if self.entity_description.property_key == "eco_shutoff_enabled":
                    ir.async_delete_issue(self.hass, DOMAIN, f"eco_shutoff_restore_{self._device._mac_addr}")
            else:
                reason = (
                    "no previous state found"
                    if last_state is None
                    else f"previous state was '{last_state.state}'"
                )
                _LOGGER.warning(
                    "%s: %s for %s, defaulting to off",
                    self._device._name,
                    reason,
                    self.entity_description.property_key,
                )
                if self.entity_description.property_key == "eco_shutoff_enabled":
                    ir.async_create_issue(
                        self.hass,
                        DOMAIN,
                        f"eco_shutoff_restore_{self._device._mac_addr}",
                        is_fixable=False,
                        severity=ir.IssueSeverity.WARNING,
                        translation_key="eco_shutoff_restore_failed",
                        translation_placeholders={"device_name": self._device._name},
                    )

    @property
    def native_value(self):
        if self.entity_description.restore_state:
            return getattr(self, "_attr_is_on", False)
        return super().native_value

    @property
    def is_on(self) -> bool:
        return bool(self.native_value)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the switch."""
        if not self.available:
            raise HomeAssistantError("Entity unavailable")

        if self.entity_description.set_fn:
            await self.entity_description.set_fn(self._device, True)

        if self.entity_description.restore_state:
            self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the switch."""
        if not self.available:
            raise HomeAssistantError("Entity unavailable")

        if self.entity_description.set_fn:
            await self.entity_description.set_fn(self._device, False)

        if self.entity_description.restore_state:
            self._attr_is_on = False
        self.async_write_ha_state()
