"""A first install seeds whole-degree presets in the user's own unit, before any stored value exists."""

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.util.unit_system import METRIC_SYSTEM, US_CUSTOMARY_SYSTEM

from .conftest import entity_id

# (heat, cool) per preset: whole °F in a US system (68 °F is exactly 20 °C), whole °C otherwise
FAHRENHEIT = {"home": (68, 75), "sleep": (62, 78), "away": (59, 82)}
CELSIUS = {"home": (20, 24), "sleep": (17, 26), "away": (15, 28)}


@pytest.mark.parametrize(("system", "defaults", "unit_shown"), [(US_CUSTOMARY_SYSTEM, FAHRENHEIT, "°F"), (METRIC_SYSTEM, CELSIUS, "°C")])
async def test_a_first_install_shows_the_defaults_in_the_users_unit(hass: HomeAssistant, unit, setup_integration, system, defaults, unit_shown):
    await setup_integration(system)
    for preset, (heat, cool) in defaults.items():
        for mode, value in (("heat", heat), ("cool", cool)):
            state = hass.states.get(entity_id(hass, "number", f"preset_{preset}_{mode}"))
            assert (float(state.state), state.attributes["unit_of_measurement"]) == (pytest.approx(value, abs=0.05), unit_shown)


@pytest.mark.parametrize(("system", "defaults", "to_celsius"), [
    (US_CUSTOMARY_SYSTEM, FAHRENHEIT, lambda f: (f - 32) * 5 / 9),
    (METRIC_SYSTEM, CELSIUS, lambda c: c),
])
async def test_the_defaults_are_held_in_celsius(hass: HomeAssistant, unit, setup_integration, system, defaults, to_celsius):
    device = await setup_integration(system)
    held = {preset: (temps["heat"], temps["cool"]) for preset, temps in device._preset_temps.items()}
    assert held == {preset: pytest.approx((to_celsius(heat), to_celsius(cool))) for preset, (heat, cool) in defaults.items()}
