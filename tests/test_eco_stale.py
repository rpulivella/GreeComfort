"""Eco Shutoff says once when its room sensor goes silent and once when it speaks again."""

import logging
from datetime import timedelta

from homeassistant.core import HomeAssistant

SILENCE = timedelta(minutes=130)


def report(hass: HomeAssistant, entity: str = "sensor.aux") -> None:
    hass.states.async_set(entity, "70.0", {"unit_of_measurement": "°F"})


async def watch(hass: HomeAssistant, device, sensor: str = "sensor.aux") -> None:
    report(hass, sensor)
    device._eco_shutoff_enabled = True
    device._eco_shutoff_sensor = sensor
    device._preset_mode = "home"


def lines(caplog, text: str) -> list[str]:
    return [r.getMessage() for r in caplog.records if text in r.getMessage()]


async def test_a_stale_sensor_is_reported_once_however_often_it_is_polled(hass: HomeAssistant, unit, setup_integration, freezer, caplog):
    device = await setup_integration()
    await watch(hass, device)
    freezer.tick(SILENCE)
    caplog.set_level(logging.INFO)
    for _ in range(6):
        await device._check_eco_shutoff()
    assert len(lines(caplog, "treating as stale")) == 1


async def test_a_recovered_sensor_is_reported_once_with_the_length_of_the_silence(hass: HomeAssistant, unit, setup_integration, freezer, caplog):
    device = await setup_integration()
    await watch(hass, device)
    freezer.tick(SILENCE)
    await device._check_eco_shutoff()
    caplog.set_level(logging.INFO)
    report(hass)
    for _ in range(3):
        await device._check_eco_shutoff()
    assert len(lines(caplog, "reporting again after 130 min of silence")) == 1


async def test_a_second_silence_is_reported_again(hass: HomeAssistant, unit, setup_integration, freezer, caplog):
    device = await setup_integration()
    await watch(hass, device)
    caplog.set_level(logging.INFO)
    for _ in range(2):
        freezer.tick(SILENCE)
        await device._check_eco_shutoff()
        report(hass)
        await device._check_eco_shutoff()
    assert (len(lines(caplog, "treating as stale")), len(lines(caplog, "reporting again"))) == (2, 2)


async def test_a_fresh_sensor_never_logs_a_recovery(hass: HomeAssistant, unit, setup_integration, caplog):
    device = await setup_integration()
    await watch(hass, device)
    caplog.set_level(logging.INFO)
    for _ in range(3):
        await device._check_eco_shutoff()
    assert lines(caplog, "stale") + lines(caplog, "reporting again") == []


async def test_changing_the_sensor_closes_the_episode_without_a_recovery_line(hass: HomeAssistant, unit, setup_integration, freezer, caplog):
    device = await setup_integration()
    await watch(hass, device)
    freezer.tick(SILENCE)
    await device._check_eco_shutoff()
    caplog.set_level(logging.INFO)
    await watch(hass, device, "sensor.other")
    await device._check_eco_shutoff()
    assert lines(caplog, "reporting again") == []


async def test_turning_eco_shutoff_off_closes_the_episode_without_a_recovery_line(hass: HomeAssistant, unit, setup_integration, freezer, caplog):
    device = await setup_integration()
    await watch(hass, device)
    freezer.tick(SILENCE)
    await device._check_eco_shutoff()
    device._eco_shutoff_enabled = False
    await device._check_eco_shutoff()
    caplog.set_level(logging.INFO)
    await watch(hass, device)
    await device._check_eco_shutoff()
    assert lines(caplog, "reporting again") == []


async def test_a_pause_in_evaluation_closes_the_episode_without_a_recovery_line(hass: HomeAssistant, unit, setup_integration, freezer, caplog):
    device = await setup_integration()
    await watch(hass, device)
    freezer.tick(SILENCE)
    await device._check_eco_shutoff()
    # Evaluation pauses (no preset), the sensor speaks again and keeps reporting for hours
    device._preset_mode = "none"
    freezer.tick(timedelta(minutes=1))
    report(hass)
    freezer.tick(timedelta(minutes=300))
    report(hass)
    await device._check_eco_shutoff()
    caplog.set_level(logging.INFO)
    device._preset_mode = "home"
    await device._check_eco_shutoff()
    assert lines(caplog, "reporting again") == []


async def test_a_silence_that_outlasts_a_pause_is_noticed_again(hass: HomeAssistant, unit, setup_integration, freezer, caplog):
    device = await setup_integration()
    await watch(hass, device)
    caplog.set_level(logging.INFO)
    freezer.tick(SILENCE)
    await device._check_eco_shutoff()
    device._preset_mode = "none"
    await device._check_eco_shutoff()
    device._preset_mode = "home"
    await device._check_eco_shutoff()
    assert len(lines(caplog, "treating as stale")) == 2
