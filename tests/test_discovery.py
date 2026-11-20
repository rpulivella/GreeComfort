"""Discovery waits for replies without blocking Home Assistant's event loop."""

import asyncio
import base64
import json
from unittest.mock import AsyncMock, patch

from Crypto.Cipher import AES
from homeassistant.core import HomeAssistant

from custom_components.gree_comfort import gree_protocol

MAC = "aabbccddeeff"


class Unit(asyncio.DatagramProtocol):
    """Answers a scan the way a Gree unit does, with an ECB pack under the generic key."""

    def connection_made(self, transport):
        self.transport = transport

    def datagram_received(self, data, addr):
        info = {"t": "dev", "mac": MAC, "name": "Test Split", "subCnt": 1, "brand": "gree", "model": "gree", "ver": "V1"}
        cipher = AES.new(gree_protocol.GENERIC_GREE_DEVICE_KEY.encode("utf8"), AES.MODE_ECB)
        pack = base64.b64encode(cipher.encrypt(gree_protocol.Pad(json.dumps(info)).encode("utf8"))).decode()
        self.transport.sendto(json.dumps({"t": "pack", "pack": pack}).encode(), addr)


async def test_discovery_finds_a_unit_without_blocking_the_event_loop(hass: HomeAssistant, socket_enabled):
    transport, _ = await asyncio.get_running_loop().create_datagram_endpoint(Unit, local_addr=("127.0.0.1", 0))
    port = transport.get_extra_info("sockname")[1]
    ticks = 0

    async def tick():
        nonlocal ticks
        while True:
            await asyncio.sleep(0.01)
            ticks += 1

    ticker = asyncio.create_task(tick())
    try:
        # Loopback only, so the test never broadcasts onto the real network.
        with (
            patch.object(gree_protocol, "DISCOVERY_PORT", port),
            patch.object(gree_protocol, "DEFAULT_BROADCAST_ADDRESSES", ("127.0.0.1",)),
            patch.object(gree_protocol, "async_get_ipv4_broadcast_addresses", new=AsyncMock(return_value=[])),
        ):
            devices = await gree_protocol.discover_gree_devices(hass, timeout=0.5)
    finally:
        ticker.cancel()
        transport.close()

    assert [(d["mac"], d["host"], d["port"]) for d in devices] == [(MAC, "127.0.0.1", port)]
    assert ticks > 20
