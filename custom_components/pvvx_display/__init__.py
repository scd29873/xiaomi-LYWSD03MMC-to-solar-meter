"""PVVX Display - write your own values to the LCD of a thermometer running pvvx/ATC firmware.

Service:  pvvx_display.show
Protocol (as used by the ESPHome pvvx_mithermometer display component):
    characteristic 00001f1f-0000-1000-8000-00805f9b34fb, write without response, 8 bytes
    [0]   0x22
    [1:3] big number    int16 LE = value * 10   (range -99.5 .. 1999.5)
    [3:5] small number  int16 LE                (range -9 .. 99)
    [5:7] validity in seconds, uint16 LE        (until then the LCD won't show its own reading;
                                                 65535 = show external data permanently)
    [7]   cfg: bit0 happy, bit1 sad, bit2 bracket, bit3 %, bit4 battery, bits5-7 unit
"""

from __future__ import annotations

import asyncio
import logging
import struct

import voluptuous as vol

from homeassistant.components import bluetooth
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)

DOMAIN = "pvvx_display"
SERVICE_SHOW = "show"

CHAR_UUID = "00001f1f-0000-1000-8000-00805f9b34fb"

UNITS = {
    "none": 0,
    "deg_ghe": 1,
    "minus": 2,
    "deg_f": 3,
    "lowdash": 4,
    "deg_c": 5,
    "lines": 6,
    "deg_e": 7,
}

CONFIG_SCHEMA = cv.empty_config_schema(DOMAIN)

SHOW_SCHEMA = vol.Schema(
    {
        vol.Required("address"): cv.string,
        vol.Optional("big", default=0.0): vol.Coerce(float),
        vol.Optional("small", default=0.0): vol.Coerce(float),
        vol.Optional("validity", default=900): vol.All(int, vol.Range(min=1, max=65535)),
        vol.Optional("unit", default="none"): vol.In(list(UNITS)),
        vol.Optional("percent", default=False): cv.boolean,
        vol.Optional("battery", default=False): cv.boolean,
        vol.Optional("happy", default=False): cv.boolean,
        vol.Optional("sad", default=False): cv.boolean,
        vol.Optional("bracket", default=False): cv.boolean,
    }
)


def build_packet(call: ServiceCall) -> bytes:
    """Build the 8-byte pvvx frame."""
    big = max(-99.5, min(1999.5, float(call.data["big"])))
    small = max(-9, min(99, int(round(float(call.data["small"])))))

    cfg = 0
    if call.data["happy"]:
        cfg |= 1 << 0
    if call.data["sad"]:
        cfg |= 1 << 1
    if call.data["bracket"]:
        cfg |= 1 << 2
    if call.data["percent"]:
        cfg |= 1 << 3
    if call.data["battery"]:
        cfg |= 1 << 4
    cfg |= (UNITS[call.data["unit"]] & 0x07) << 5

    return struct.pack(
        "<BhhHB",
        0x22,
        int(round(big * 10)),
        small,
        int(call.data["validity"]),
        cfg,
    )


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the pvvx_display.show service."""
    lock = asyncio.Lock()

    async def handle_show(call: ServiceCall) -> None:
        from bleak_retry_connector import BleakClientWithServiceCache, establish_connection

        address = call.data["address"].upper()
        payload = build_packet(call)

        async with lock:  # one write at a time, BLE adapters don't like parallel connections
            ble_device = bluetooth.async_ble_device_from_address(hass, address, connectable=True)
            if ble_device is None:
                raise HomeAssistantError(
                    f"{address} is not in Bluetooth range (or not connectable)"
                )

            client = None
            try:
                client = await establish_connection(
                    BleakClientWithServiceCache, ble_device, address, max_attempts=3
                )
                await client.write_gatt_char(CHAR_UUID, payload, response=False)
                _LOGGER.debug("%s: wrote %s", address, payload.hex())
            except Exception as err:  # noqa: BLE001
                raise HomeAssistantError(f"write to {address} failed: {err}") from err
            finally:
                if client is not None:
                    try:
                        await client.disconnect()
                    except Exception:  # noqa: BLE001
                        pass

    hass.services.async_register(DOMAIN, SERVICE_SHOW, handle_show, schema=SHOW_SCHEMA)
    _LOGGER.info("PVVX Display ready, service %s.%s registered", DOMAIN, SERVICE_SHOW)
    return True
