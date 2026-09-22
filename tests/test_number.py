"""Number entities: HA-native units, restore migration and RestoreNumber round trips."""

import pytest
from homeassistant.core import HomeAssistant, State
from homeassistant.util.unit_system import METRIC_SYSTEM
from pytest_homeassistant_custom_component.common import mock_restore_cache, mock_restore_cache_with_extra_data

from .conftest import entity_id

PRESETS = [
    ("preset_home_heat", "climate_control_test_split_home_heat_temperature", "66.0", 18.89),
    ("preset_sleep_heat", "climate_control_test_split_sleep_heat_temperature", "60.8", 16.0),
    ("preset_home_cool", "climate_control_test_split_home_cool_temperature", "75.0", 23.89),
]
DELTAS = [
    ("eco_shutoff_satisfied_margin", "climate_control_test_split_eco_shutoff_satisfied_margin", "4.5", 2.5),
    ("eco_shutoff_reengage_delta", "climate_control_test_split_eco_shutoff_re_engage_delta", "2.2", 1.22),
]


async def test_states_saved_before_1_1_0_migrate_by_their_recorded_unit(hass: HomeAssistant, pin_entity, setup_integration):
    for key, object_id, _, _ in PRESETS + DELTAS:
        pin_entity("number", key, object_id)
    mock_restore_cache(hass, [State(f"number.{obj}", value, {"unit_of_measurement": "°F"}) for _, obj, value, _ in PRESETS + DELTAS])
    device = await setup_integration()

    assert device._preset_temps["home"]["heat"] == pytest.approx(18.89)
    assert device._preset_temps["sleep"]["heat"] == pytest.approx(16.0)
    assert device._preset_temps["home"]["cool"] == pytest.approx(23.89)
    assert device._eco_shutoff_satisfied_margin == pytest.approx(2.5)
    assert device._eco_shutoff_reengage_delta == pytest.approx(1.22)
    for key, _, value, _ in PRESETS + DELTAS:
        state = hass.states.get(entity_id(hass, "number", key))
        assert float(state.state) == pytest.approx(float(value), abs=0.05), key
        assert state.attributes["unit_of_measurement"] == "°F"


async def test_restore_number_data_round_trips(hass: HomeAssistant, pin_entity, setup_integration):
    pin_entity("number", "preset_home_heat", PRESETS[0][1])
    pin_entity("number", "eco_shutoff_satisfied_margin", DELTAS[0][1])
    mock_restore_cache_with_extra_data(hass, [
        (State(f"number.{PRESETS[0][1]}", "66.0", {"unit_of_measurement": "°F"}),
         {"native_max_value": 30, "native_min_value": 16, "native_step": 0.5, "native_unit_of_measurement": "°C", "native_value": 18.89}),
        (State(f"number.{DELTAS[0][1]}", "4.5", {"unit_of_measurement": "°F"}),
         {"native_max_value": 9.0, "native_min_value": 1.8, "native_step": 0.9, "native_unit_of_measurement": "°F", "native_value": 4.5}),
    ])
    device = await setup_integration()
    assert device._preset_temps["home"]["heat"] == pytest.approx(18.89)
    assert device._eco_shutoff_satisfied_margin == pytest.approx(2.5)


async def test_bounds_display_in_the_system_unit(hass: HomeAssistant, setup_integration):
    await setup_integration()
    home_heat = hass.states.get(entity_id(hass, "number", "preset_home_heat"))
    # 61 °F, not 60.8, so whole-degree steps land on whole degrees; the unit encodes both the same
    assert (home_heat.attributes["min"], home_heat.attributes["max"], home_heat.attributes["step"]) == (61.0, 86.0, 1.0)
    margin = hass.states.get(entity_id(hass, "number", "eco_shutoff_satisfied_margin"))
    assert (margin.attributes["min"], margin.attributes["max"]) == (1.8, 9.0)


async def test_setting_values_in_fahrenheit_stores_celsius(hass: HomeAssistant, setup_integration):
    device = await setup_integration()
    await hass.services.async_call("number", "set_value",
                                   {"entity_id": entity_id(hass, "number", "preset_home_heat"), "value": 68}, blocking=True)
    assert device._preset_temps["home"]["heat"] == pytest.approx(20.0)
    assert float(hass.states.get(entity_id(hass, "number", "preset_home_heat")).state) == pytest.approx(68.0)
    await hass.services.async_call("number", "set_value",
                                   {"entity_id": entity_id(hass, "number", "eco_shutoff_reengage_delta"), "value": 1.8}, blocking=True)
    assert device._eco_shutoff_reengage_delta == pytest.approx(1.0)


async def test_changing_the_active_preset_reapplies_it(hass: HomeAssistant, unit, setup_integration):
    unit.state.update(Mod=4, SetTem=19, TemRec=0)
    device = await setup_integration()
    device._preset_mode = "home"
    await hass.services.async_call("number", "set_value",
                                   {"entity_id": entity_id(hass, "number", "preset_home_heat"), "value": 70}, blocking=True)
    assert unit.sent("SetTem")[-1] == 21  # 70°F
    assert device._manual_override is False


@pytest.mark.parametrize("fahrenheit", [round(61 + i / 10, 1) for i in range(251)])
async def test_every_fahrenheit_preset_displays_exactly(hass: HomeAssistant, setup_integration, fahrenheit):
    await setup_integration()
    await hass.services.async_call("number", "set_value",
                                   {"entity_id": entity_id(hass, "number", "preset_home_heat"), "value": fahrenheit}, blocking=True)
    assert hass.states.get(entity_id(hass, "number", "preset_home_heat")).state == str(fahrenheit)


async def test_a_value_saved_by_1_1_2_as_rounded_celsius_displays_cleanly(hass: HomeAssistant, pin_entity, setup_integration):
    pin_entity("number", "preset_sleep_cool", "climate_control_test_split_sleep_cool_temperature")
    mock_restore_cache_with_extra_data(hass, [(
        State("number.climate_control_test_split_sleep_cool_temperature", "78.01", {"unit_of_measurement": "°F"}),
        {"native_max_value": 30, "native_min_value": 16, "native_step": 0.5, "native_unit_of_measurement": "°C", "native_value": 25.56},
    )])
    await setup_integration()
    assert hass.states.get(entity_id(hass, "number", "preset_sleep_cool")).state == "78.0"


async def test_preset_step_matches_the_unit_resolution(hass: HomeAssistant, setup_integration):
    await setup_integration()
    assert hass.states.get(entity_id(hass, "number", "preset_home_heat")).attributes["step"] == 1.0


async def test_presets_display_in_celsius_on_a_metric_system(hass: HomeAssistant, setup_integration):
    await setup_integration(METRIC_SYSTEM)
    state = hass.states.get(entity_id(hass, "number", "preset_home_heat"))
    assert (state.state, state.attributes["unit_of_measurement"], state.attributes["step"]) == ("20.0", "°C", 0.5)


async def test_a_saved_preset_below_the_whole_degree_minimum_still_displays(hass: HomeAssistant, pin_entity, setup_integration):
    pin_entity("number", "preset_sleep_heat", "climate_control_test_split_sleep_heat_temperature")
    mock_restore_cache(hass, [State("number.climate_control_test_split_sleep_heat_temperature", "60.8", {"unit_of_measurement": "°F"})])
    device = await setup_integration()
    assert hass.states.get(entity_id(hass, "number", "preset_sleep_heat")).state == "60.8"
    assert device._preset_temps["sleep"]["heat"] == pytest.approx(16.0)
