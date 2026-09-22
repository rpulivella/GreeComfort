"""Config and options flows, with the network helpers the flow calls patched out."""

from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.gree_comfort.const import DOMAIN

FLOW = "custom_components.gree_comfort.config_flow"
MANUAL = {"name": "Basement", "host": "10.0.0.2", "mac": "aabbccddeeff", "port": 7000, "encryption_key": "", "encryption_version": 1}
FOUND = {"name": "gree", "host": "10.0.0.2", "mac": "aabbccddeeff", "port": 7000}


@pytest.fixture(autouse=True)
def skip_entry_setup():
    """Creating an entry would set the integration up; these tests stop at the entry."""
    with patch("custom_components.gree_comfort.async_setup_entry", AsyncMock(return_value=True)):
        yield


async def start(hass: HomeAssistant, method: str):
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "user"
    return await hass.config_entries.flow.async_configure(result["flow_id"], {"discovery": method})


async def test_manual_entry_creates_the_entry(hass: HomeAssistant):
    result = await start(hass, "manual")
    assert result["step_id"] == "manual"
    with patch(f"{FLOW}.test_connection", AsyncMock(return_value=True)):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], MANUAL)
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Basement"
    assert result["data"]["mac"] == "aabbccddeeff"


async def test_manual_entry_reports_an_unreachable_unit_then_recovers(hass: HomeAssistant):
    result = await start(hass, "manual")
    with patch(f"{FLOW}.test_connection", AsyncMock(return_value=False)):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], MANUAL)
    assert result["type"] is FlowResultType.FORM and result["errors"] == {"base": "cannot_connect"}
    with patch(f"{FLOW}.test_connection", AsyncMock(return_value=True)):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], MANUAL)
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_manual_entry_aborts_on_a_configured_unit(hass: HomeAssistant):
    MockConfigEntry(domain=DOMAIN, unique_id="aabbccddeeff", data=MANUAL).add_to_hass(hass)
    result = await start(hass, "manual")
    result = await hass.config_entries.flow.async_configure(result["flow_id"], MANUAL)
    assert result["type"] is FlowResultType.ABORT and result["reason"] == "already_configured"


async def test_discovery_with_nothing_found_falls_back_to_manual(hass: HomeAssistant):
    with patch(f"{FLOW}.discover_gree_devices", AsyncMock(return_value=[])):
        result = await start(hass, "discover")
    assert result["step_id"] == "manual"


async def test_discovered_unit_is_named_and_created(hass: HomeAssistant):
    with patch(f"{FLOW}.discover_gree_devices", AsyncMock(return_value=[FOUND])):
        result = await start(hass, "discover")
    assert result["step_id"] == "discovery"
    with patch(f"{FLOW}.detect_device_encryption", AsyncMock(return_value=2)):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"device": "aabbccddeeff_10.0.0.2"})
    assert result["step_id"] == "detect_encryption"
    with patch(f"{FLOW}.test_connection", AsyncMock(return_value=True)):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"name": "Basement"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"]["encryption_version"] == 2


async def test_undetectable_encryption_falls_back_to_manual_with_an_error(hass: HomeAssistant):
    with patch(f"{FLOW}.discover_gree_devices", AsyncMock(return_value=[FOUND])):
        result = await start(hass, "discover")
    with patch(f"{FLOW}.detect_device_encryption", AsyncMock(return_value=None)):
        result = await hass.config_entries.flow.async_configure(result["flow_id"], {"device": "aabbccddeeff_10.0.0.2"})
    assert result["step_id"] == "manual" and result["errors"] == {"base": "cannot_connect"}


async def test_options_flow_saves_known_keys_and_clears_empty_ones(hass: HomeAssistant):
    entry = MockConfigEntry(domain=DOMAIN, unique_id="aabbccddeeff", data=MANUAL, options={"temp_sensor_offset": True})
    entry.add_to_hass(hass)
    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM and result["step_id"] == "init"
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"hvac_modes": ["cool", "heat"], "disable_available_check": False})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options["hvac_modes"] == ["cool", "heat"]
    assert entry.options["temp_sensor_offset"] is None  # left out of the form, so cleared
