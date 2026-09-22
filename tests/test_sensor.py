"""Sensors report native °C and HA converts them."""

from pathlib import Path

import pytest
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers.entity_component import async_update_entity
from pytest_homeassistant_custom_component.common import mock_restore_cache

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


async def test_eco_sensor_select_keeps_its_choice_before_the_sensor_loads(hass: HomeAssistant, pin_entity, setup_integration):
    pin_entity("select", "eco_shutoff_sensor", "climate_control_test_split_eco_shutoff_temperature_sensor")
    mock_restore_cache(hass, [State("select.climate_control_test_split_eco_shutoff_temperature_sensor", "sensor.late_zigbee", {})])
    device = await setup_integration()  # sensor.late_zigbee does not exist yet
    assert device._eco_shutoff_sensor == "sensor.late_zigbee"
    assert hass.states.get(entity_id(hass, "select", "eco_shutoff_sensor")).state == "sensor.late_zigbee"


async def test_brand_images_are_served_from_the_integration(hass: HomeAssistant, setup_integration):
    from homeassistant.loader import async_get_custom_components

    await setup_integration()
    integration = (await async_get_custom_components(hass))["gree_comfort"]
    assert integration.has_branding
    brand = Path(integration.file_path) / "brand"
    assert (brand / "icon.png").is_file() and (brand / "logo.png").is_file()
