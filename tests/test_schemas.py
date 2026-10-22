"""The service and YAML schemas, which Home Assistant validates before any integration code runs."""

import probatio
import pytest
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from custom_components.gree_comfort import CONFIG_SCHEMA
from custom_components.gree_comfort.const import DEFAULT_PORT, DOMAIN

YAML_UNIT = {"name": "Basement", "host": "10.0.0.2", "mac": "aabbccddeeff"}


async def test_scheduled_preset_service_stores_a_known_preset(hass: HomeAssistant, unit, setup_integration):
    device = await setup_integration()
    await hass.services.async_call(DOMAIN, "set_scheduled_preset", {"preset_mode": "sleep"}, blocking=True)
    assert device._scheduled_preset == "sleep"


async def test_scheduled_preset_service_rejects_an_unknown_preset(hass: HomeAssistant, unit, setup_integration):
    device = await setup_integration()
    before = device._scheduled_preset
    with pytest.raises(probatio.Invalid):
        await hass.services.async_call(DOMAIN, "set_scheduled_preset", {"preset_mode": "eco"}, blocking=True)
    assert device._scheduled_preset == before


def test_yaml_unit_gets_its_defaults():
    unit = CONFIG_SCHEMA({DOMAIN: YAML_UNIT})[DOMAIN][0]
    assert (unit["port"], unit["encryption_version"], unit["disable_available_check"]) == (DEFAULT_PORT, 1, False)


@pytest.mark.parametrize("bad", [{"encryption_version": 3}, {"host": None}, {"port": "high"}])
async def test_yaml_unit_with_a_bad_value_is_refused(hass: HomeAssistant, bad):
    assert not await async_setup_component(hass, DOMAIN, {DOMAIN: [{**YAML_UNIT, **bad}]})
