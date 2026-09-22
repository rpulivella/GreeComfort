"""Climate entity: units, setpoints, eco shutoff, manual override, smart 8°C and hvac_action."""

from datetime import timedelta
from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_system import METRIC_SYSTEM

from .conftest import climate_id


async def test_fahrenheit_display(hass: HomeAssistant, unit, setup_integration):
    await setup_integration()
    state = hass.states.get(climate_id(hass))
    # SetTem 24/0 is how the unit encodes 75°F; TemSen 21°C is 69.8°F
    assert state.attributes["temperature"] == 75
    assert state.attributes["current_temperature"] == 70
    assert (state.attributes["min_temp"], state.attributes["max_temp"]) == (61, 86)


@pytest.mark.parametrize(("fahrenheit", "encoded"), [(66, (19, 0)), (61, (16, 1)), (75, (24, 0)), (82, (28, 0))])
async def test_fahrenheit_setpoints_reach_the_unit(hass: HomeAssistant, unit, setup_integration, fahrenheit, encoded):
    await setup_integration()
    await hass.services.async_call("climate", "set_temperature",
                                   {"entity_id": climate_id(hass), "temperature": fahrenheit}, blocking=True)
    assert (unit.sent("SetTem")[-1], unit.sent("TemRec")[-1]) == encoded
    assert hass.states.get(climate_id(hass)).attributes["temperature"] == fahrenheit


async def test_celsius_setpoints_reach_the_unit(hass: HomeAssistant, unit, setup_integration):
    await setup_integration(METRIC_SYSTEM)
    await hass.services.async_call("climate", "set_temperature",
                                   {"entity_id": climate_id(hass), "temperature": 21.5}, blocking=True)
    assert (unit.sent("SetTem")[-1], unit.sent("TemRec")[-1]) == (21, 1)
    state = hass.states.get(climate_id(hass))
    assert (state.attributes["temperature"], state.attributes["current_temperature"]) == (21.5, 21.0)


async def run_eco(device, aux_state):
    device.hass.states.async_set("sensor.aux", *aux_state)
    device._eco_shutoff_enabled = True
    device._eco_shutoff_sensor = "sensor.aux"
    device._preset_mode = "home"
    await device.async_update()
    if device._eco_shutoff_satisfied_since is not None:
        device._eco_shutoff_satisfied_since = dt_util.utcnow() - timedelta(minutes=30)
    await device.async_update()


@pytest.mark.parametrize(
    ("mod", "set_tem", "tem_rec", "aux_f", "fires"),
    [
        (4, 16, 1, "68.0", True),   # heat at 61°F, room 7°F warmer than setpoint
        (4, 16, 1, "62.0", False),
        (1, 24, 0, "71.2", False),  # the live false firing of 21 Sep 2026
        (1, 24, 0, "70.0", True),
    ],
)
async def test_eco_thresholds_compare_in_one_unit(hass: HomeAssistant, unit, setup_integration, mod, set_tem, tem_rec, aux_f, fires):
    unit.state.update(Mod=mod, SetTem=set_tem, TemRec=tem_rec)
    device = await setup_integration()
    device._eco_shutoff_satisfied_margin = 2.5  # live value, shown as 4.5°F
    await run_eco(device, (aux_f, {"unit_of_measurement": "°F"}))
    assert device._eco_shutoff_active is fires
    assert (0 in unit.sent("Pow")) is fires


async def test_eco_accepts_a_kelvin_sensor(hass: HomeAssistant, unit, setup_integration):
    device = await setup_integration()
    await run_eco(device, ("294.15", {"unit_of_measurement": "K"}))  # 21°C, cool at 75°F
    assert device._eco_shutoff_active is True


async def test_eco_restores_power_when_the_room_drifts_back(hass: HomeAssistant, unit, setup_integration):
    device = await setup_integration()
    await run_eco(device, ("70.0", {"unit_of_measurement": "°F"}))
    assert device._eco_shutoff_active is True
    hass.states.async_set("sensor.aux", "77.5", {"unit_of_measurement": "°F"})  # past 75°F + 1.2°F
    await device.async_update()
    assert device._eco_shutoff_active is False
    assert unit.sent("Pow")[-1] == 1


async def test_manual_override_uses_the_exact_encoding(hass: HomeAssistant, unit, setup_integration):
    unit.state.update(Mod=4, SetTem=16, TemRec=1)
    device = await setup_integration()
    device._preset_mode = "sleep"
    device._preset_temps["sleep"]["heat"] = 16.0  # 60.8°F preset, which the unit shows as 61°F
    device._recalculate_manual_override()
    assert device._manual_override is False
    device._acOptions["SetTem"] = 17
    device._recalculate_manual_override()
    assert device._manual_override is True


async def test_smart_8c_is_cleared_with_the_mode_change(hass: HomeAssistant, unit, setup_integration):
    unit.state.update(Mod=4, StHt=1)
    device = await setup_integration()
    device._stht_smart_active = True
    await hass.services.async_call("climate", "set_hvac_mode",
                                   {"entity_id": climate_id(hass), "hvac_mode": "cool"}, blocking=True)
    first = unit.commands[0]
    assert (first["Mod"], first["StHt"]) == (1, 0)
    assert device._stht_smart_active is False
    assert hass.states.get(climate_id(hass)).attributes["temperature"] != 46


async def test_hvac_action_follows_settled_temsen_steps(hass: HomeAssistant, unit, setup_integration):
    unit.state.update(Mod=4, SetTem=19, TemSen=20)
    device = await setup_integration()
    now = [dt_util.utcnow()]

    async def poll(minutes, **state):
        unit.state.update(state)
        with patch("custom_components.gree_comfort.climate.dt_util.utcnow", lambda: now[0]):
            for _ in range(int(minutes * 6)):
                now[0] += timedelta(seconds=10)
                await device.async_update()
        return device.hvac_action

    assert await poll(5) == "idle"
    assert await poll(2, TemSen=21) == "idle"        # not settled yet
    assert await poll(2) == "heating"                # settled after 3 min
    assert await poll(2, TemSen=20) == "heating"     # step back not settled yet
    assert await poll(2) == "idle"
    assert await poll(1, Pow=0) == "off"
    assert await poll(3, Pow=1, TemSen=19) == "idle"  # power-on dip is ignored
    device._eco_shutoff_active = True
    assert device.hvac_action == "idle"


async def test_unit_offline_marks_the_entity_unavailable(hass: HomeAssistant, unit, setup_integration):
    device = await setup_integration()
    unit.online = False
    with patch("custom_components.gree_comfort.gree_protocol.asyncio.sleep"):
        await device.async_update()
    assert device.available is False


async def test_first_command_after_an_offline_startup_reaches_the_unit(hass: HomeAssistant, unit, setup_integration):
    unit.online = False  # HA starts while the unit is unreachable, as after a power outage
    device = await setup_integration()
    unit.online = True
    await device.SyncState({"Lig": 1})
    assert unit.sent("Lig") == [1]
