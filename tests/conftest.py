"""Shared fixtures: a simulated Gree unit answering at the network boundary."""

from __future__ import annotations

import base64
import json
from collections.abc import Callable
from typing import Any
from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.entity_component import async_update_entity
from homeassistant.util.unit_system import US_CUSTOMARY_SYSTEM, UnitSystem
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.gree_comfort.climate import GreeClimate
from custom_components.gree_comfort.const import DOMAIN

MAC = "aabbccddeeff"
KEY = "abcdefghijklmnop"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Load custom_components/ in every test."""
    yield


class FakeUnit:
    """A Gree unit that decrypts real request packs and answers status and cmd packets."""

    def __init__(self) -> None:
        self.state: dict[str, Any] = {
            "Pow": 1, "Mod": 1, "SetTem": 24, "TemRec": 0, "WdSpd": 0, "Air": 0, "Blo": 0,
            "Health": 0, "SwhSlp": 0, "Lig": 0, "SwingLfRig": 0, "SwUpDn": 0, "Quiet": 0,
            "Tur": 0, "StHt": 0, "TemUn": 1, "HeatCoolType": 0, "SvSt": 0, "SlpMod": 0,
            "TemSen": 21, "OutEnvTem": 21, "DwatSen": 50, "AntiDirectBlow": 0, "LigSen": 0,
        }
        self.commands: list[dict[str, Any]] = []
        self.online = True

    async def fetch(self, cipher, ip_addr, port, json_data, encryption_version=1, max_retries=8):
        if not self.online:
            raise TimeoutError("simulated unit offline")
        packet = json.loads(json_data)
        plain = cipher.decrypt(base64.b64decode(packet["pack"])).decode("utf-8")
        request = json.loads(plain[: plain.rindex("}") + 1])
        if request["t"] == "status":
            return {"t": "dat", "cols": request["cols"], "dat": [self.state.get(c, 0) for c in request["cols"]]}
        if request["t"] == "cmd":
            sent = dict(zip(request["opt"], request["p"], strict=True))
            self.commands.append(sent)
            self.state.update({k: v for k, v in sent.items() if k in self.state})
            return {"t": "res", "r": 200, "opt": request["opt"], "p": request["p"]}
        raise AssertionError(f"unexpected packet {request}")

    def sent(self, key: str) -> list[Any]:
        """Every value sent for one key, oldest first."""
        return [command[key] for command in self.commands if key in command]


@pytest.fixture
def unit() -> FakeUnit:
    return FakeUnit()


@pytest.fixture
def pin_entity(hass: HomeAssistant) -> Callable[[str, str, str], None]:
    """Pre-register an entity id, so restore-cache keys match regardless of harness naming."""

    def pin(platform: str, key: str, object_id: str) -> None:
        er.async_get(hass).async_get_or_create(platform, DOMAIN, f"{MAC}_{key}", suggested_object_id=object_id)

    return pin


@pytest.fixture
def setup_integration(hass: HomeAssistant, unit: FakeUnit):
    """Return a coroutine that loads the integration against the simulated unit."""

    async def setup(units: UnitSystem = US_CUSTOMARY_SYSTEM, **data: Any) -> GreeClimate:
        hass.config.units = units
        entry = MockConfigEntry(domain=DOMAIN, unique_id=MAC, data={
            "name": "Test Split", "host": "10.0.0.2", "mac": MAC, "port": 7000,
            "encryption_key": KEY, "encryption_version": 1, "temp_sensor_offset": False,
            **data,
        })
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        device: GreeClimate = hass.data[DOMAIN][entry.entry_id]["device"]
        # First poll: SyncState only reads on its first run, so later commands are sent
        await device.async_update()
        device.async_write_ha_state()
        for registered in er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id):
            await async_update_entity(hass, registered.entity_id)
        await hass.async_block_till_done()
        return device

    with patch("custom_components.gree_comfort.climate.FetchResult", unit.fetch):
        yield setup


def entity_id(hass: HomeAssistant, platform: str, key: str) -> str:
    return er.async_get(hass).async_get_entity_id(platform, DOMAIN, f"{MAC}_{key}")


def climate_id(hass: HomeAssistant) -> str:
    return er.async_get(hass).async_get_entity_id("climate", DOMAIN, f"{DOMAIN}_{MAC}")
