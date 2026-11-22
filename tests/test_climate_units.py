"""What Home Assistant shows for the climate entity's temperatures, in each unit system.

The entity reports native °C and Home Assistant converts. These tests pin the converted values a
user sees, so the property names the entity uses to report them can change without a number moving.
"""

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.util.unit_system import METRIC_SYSTEM, US_CUSTOMARY_SYSTEM

from .conftest import climate_id, entity_id


async def set_target(hass: HomeAssistant, value: float) -> dict:
    await hass.services.async_call("climate", "set_temperature",
                                   {"entity_id": climate_id(hass), "temperature": value}, blocking=True)
    return dict(hass.states.get(climate_id(hass)).attributes)


# (asked for, shown), in °F. A half degree rounds to the even whole degree at the protocol boundary.
FAHRENHEIT = [(61, 61), (61.5, 62), (66, 66), (72.5, 72), (75, 75), (86, 86)]
CELSIUS = [(16, 16.0), (16.5, 16.5), (21.5, 21.5), (24, 24.0), (25.56, 25.5), (30, 30.0)]


@pytest.mark.parametrize(("asked", "shown"), FAHRENHEIT)
async def test_fahrenheit_system_shows_the_setpoint_and_the_unchanging_limits(hass: HomeAssistant, unit, setup_integration, asked, shown):
    await setup_integration(US_CUSTOMARY_SYSTEM)
    attributes = await set_target(hass, asked)
    # TemSen 21°C is a room at 69.8°F, which the entity shows as whole degrees
    assert (attributes["temperature"], attributes["current_temperature"]) == (shown, 70)
    assert (attributes["min_temp"], attributes["max_temp"], attributes["target_temp_step"]) == (61, 86, 1)


@pytest.mark.parametrize(("asked", "shown"), CELSIUS)
async def test_celsius_system_shows_the_setpoint_and_the_unchanging_limits(hass: HomeAssistant, unit, setup_integration, asked, shown):
    await setup_integration(METRIC_SYSTEM)
    attributes = await set_target(hass, asked)
    assert (attributes["temperature"], attributes["current_temperature"]) == (shown, 21)
    assert (attributes["min_temp"], attributes["max_temp"], attributes["target_temp_step"]) == (16, 30, 1)


@pytest.mark.parametrize("system", [US_CUSTOMARY_SYSTEM, METRIC_SYSTEM])
async def test_a_sensor_offset_never_reaches_the_displayed_room_temperature(hass: HomeAssistant, unit, setup_integration, system):
    # With the offset on, the unit reports its own reading 40 degrees too high
    unit.state["TemSen"] = 61
    await setup_integration(system, temp_sensor_offset=True)
    expected = 70 if system is US_CUSTOMARY_SYSTEM else 21
    assert hass.states.get(climate_id(hass)).attributes["current_temperature"] == expected


@pytest.mark.parametrize(("system", "outside", "unit_shown"), [(US_CUSTOMARY_SYSTEM, "69.8", "°F"), (METRIC_SYSTEM, "21", "°C")])
async def test_temperature_sensors_follow_the_unit_system(hass: HomeAssistant, unit, setup_integration, system, outside, unit_shown):
    await setup_integration(system)
    for key in ("outside_temperature", "eco_shutoff_temperature"):
        state = hass.states.get(entity_id(hass, "sensor", key))
        assert state.attributes["unit_of_measurement"] == unit_shown, key
    assert hass.states.get(entity_id(hass, "sensor", "outside_temperature")).state == outside


async def test_the_entity_reports_native_celsius(hass: HomeAssistant, unit, setup_integration):
    device = await setup_integration(US_CUSTOMARY_SYSTEM)
    assert device.native_temperature_unit == "°C"
    # TemSen 21°C is the room, and the unit's 75°F setpoint is exactly (75 - 32) * 5 / 9 in °C
    assert device.native_current_temperature == 21
    assert device.native_target_temperature == pytest.approx((75 - 32) * 5 / 9)
