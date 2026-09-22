"""Sensors report native °C and HA converts them."""

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_component import async_update_entity

from .conftest import entity_id


async def test_outside_temperature_is_converted_by_ha(hass: HomeAssistant, setup_integration):
    await setup_integration()
    state = hass.states.get(entity_id(hass, "sensor", "outside_temperature"))
    assert state.attributes["unit_of_measurement"] == "°F"
    assert float(state.state) == pytest.approx(69.8, abs=0.05)


@pytest.mark.parametrize(("value", "unit_of_measurement"), [("294.15", "K"), ("69.8", "°F"), ("21.0", "°C")])
async def test_eco_temperature_accepts_any_temperature_unit(hass: HomeAssistant, setup_integration, value, unit_of_measurement):
    device = await setup_integration()
    hass.states.async_set("sensor.aux", value, {"unit_of_measurement": unit_of_measurement})
    device._eco_shutoff_sensor = "sensor.aux"
    eco_temp = entity_id(hass, "sensor", "eco_shutoff_temperature")
    await async_update_entity(hass, eco_temp)
    state = hass.states.get(eco_temp)
    assert state.attributes["unit_of_measurement"] == "°F"
    assert float(state.state) == pytest.approx(69.8, abs=0.05)


async def test_eco_temperature_ignores_a_sensor_without_a_temperature_unit(hass: HomeAssistant, setup_integration):
    device = await setup_integration()
    hass.states.async_set("sensor.aux", "50", {"unit_of_measurement": "%"})
    device._eco_shutoff_sensor = "sensor.aux"
    eco_temp = entity_id(hass, "sensor", "eco_shutoff_temperature")
    await async_update_entity(hass, eco_temp)
    assert hass.states.get(eco_temp).state == "unknown"
