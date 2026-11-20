"""A device encryption key is a secret, so no log level may print it."""

import logging
from unittest.mock import patch

import pytest

from custom_components.gree_comfort import gree_protocol

from .conftest import KEY

DEVICE_KEY = "q1w2e3r4t5y6u7i8"
UNIT = {"host": "10.0.0.2", "port": 7000, "mac": "aabbccddeeff", "encryption_key": KEY, "encryption_version": 1}


async def bind_response(*args, **kwargs):
    return {"t": "bindok", "mac": "aabbccddeeff", "key": DEVICE_KEY}


@pytest.fixture
def everything_logged(caplog):
    caplog.set_level(logging.DEBUG)
    return caplog


@pytest.mark.parametrize("fetch_key", [gree_protocol.GetDeviceKey, gree_protocol.GetDeviceKeyGCM])
async def test_a_fetched_device_key_is_never_logged(everything_logged, fetch_key):
    with patch.object(gree_protocol, "FetchResult", bind_response):
        assert await fetch_key("aabbccddeeff", "10.0.0.2", 7000) == DEVICE_KEY.encode()
    assert DEVICE_KEY not in everything_logged.text


@pytest.mark.parametrize("version", [1, 2])
async def test_a_connection_test_never_logs_a_key(everything_logged, version):
    with patch.object(gree_protocol, "FetchResult", bind_response):
        assert await gree_protocol.test_connection({**UNIT, "encryption_version": version})
    assert DEVICE_KEY not in everything_logged.text
    assert KEY not in everything_logged.text


async def test_setting_up_a_unit_with_a_configured_key_never_logs_it(everything_logged, setup_integration):
    await setup_integration()
    assert KEY not in everything_logged.text
