"""Pure helpers: setpoint encoding, the TemSen step tracker and the offset resolver."""

from datetime import UTC, datetime, timedelta

import pytest

from custom_components.gree_comfort.helpers import (
    TempOffsetResolver,
    TemSenStepTracker,
    decode_temp_c,
    encode_temp_c,
    gree_c_to_f,
    gree_f_to_c,
)

T0 = datetime(2026, 9, 21, 8, 0, tzinfo=UTC)
HEAT, COOL = 1, -1
HEAT_TIMEOUT, COOL_TIMEOUT = 35 * 60, 60 * 60


def f_to_c(f: float) -> float:
    return (f - 32) / 1.8


@pytest.mark.parametrize("fahrenheit", range(61, 87))
def test_whole_fahrenheit_setpoints_round_trip(fahrenheit):
    set_tem, tem_rec = gree_f_to_c(fahrenheit)
    assert gree_c_to_f(set_tem, tem_rec) == fahrenheit
    assert gree_f_to_c(gree_c_to_f(set_tem, tem_rec)) == (set_tem, tem_rec)


@pytest.mark.parametrize("celsius", [x / 2 for x in range(32, 61)])
def test_half_celsius_setpoints_round_trip(celsius):
    assert decode_temp_c(*encode_temp_c(celsius)) == celsius


@pytest.mark.parametrize(("fahrenheit", "encoded"), [(61, (16, 1)), (66, (19, 0)), (75, (24, 0)), (78, (26, 0)), (82, (28, 0))])
def test_fahrenheit_encodings_match_the_live_unit(fahrenheit, encoded):
    assert gree_f_to_c(fahrenheit) == encoded


def test_offset_resolver_detects_offset_readings():
    resolver = TempOffsetResolver()
    assert resolver(61) == 21  # 61 is implausible indoors, so the +40 offset applies
    assert resolver(62) == 22


def run(tracker, segments, direction, timeout, start=T0):
    """Feed (minutes, value) segments at the 10 s poll rate; return (minute, active) per poll."""
    out, now = [], start
    for minutes, value in segments:
        for _ in range(int(minutes * 6)):
            out.append(((now - start).total_seconds() / 60, tracker.update(value, direction, timeout, now)))
            now += timedelta(seconds=10)
    return out


def active_minutes(trace):
    return sum(1 for _, active in trace if active) / 6


def first_change(trace, to):
    return next(minute for minute, active in trace if active is to)


def test_flicker_never_settles():
    trace = run(TemSenStepTracker(), [(10, 20)] + [(1, 21), (1, 20)] * 20, HEAT, HEAT_TIMEOUT)
    assert active_minutes(trace) == 0


def test_heat_run_starts_and_ends_on_settled_steps():
    tracker = TemSenStepTracker()
    trace = run(tracker, [(10, 20), (20, 21), (20, 20)], HEAT, HEAT_TIMEOUT)
    assert 12.9 <= first_change(trace, True) <= 13.1
    assert 32.9 <= first_change([x for x in trace if x[0] > 20], False) <= 33.1
    assert tracker.active_since is None


def test_run_start_is_backdated_to_first_appearance():
    tracker = TemSenStepTracker()
    run(tracker, [(10, 20), (5, 21)], HEAT, HEAT_TIMEOUT)
    assert tracker.active_since == T0 + timedelta(minutes=10)


def test_room_drift_step_times_out():
    trace = run(TemSenStepTracker(), [(10, 20), (120, 21)], HEAT, HEAT_TIMEOUT)
    assert 44.9 <= first_change([x for x in trace if x[0] > 13], False) <= 45.1
    assert 31.5 <= active_minutes(trace) <= 32.5


def test_consecutive_toward_steps_refresh_the_timeout():
    trace = run(TemSenStepTracker(), [(10, 20), (30, 21), (30, 22), (10, 22)], HEAT, HEAT_TIMEOUT)
    assert all(active for minute, active in trace if 13.2 <= minute < 75)
    assert not trace[-1][1]  # the second step is backdated to 40 min and times out at 75


def test_away_step_in_cool_is_idle():
    trace = run(TemSenStepTracker(), [(10, 24), (30, 25)], COOL, COOL_TIMEOUT)
    assert active_minutes(trace) == 0


def test_cool_run_held_54_minutes_stays_cooling():
    trace = run(TemSenStepTracker(), [(10, 22), (54, 21), (20, 22)], COOL, COOL_TIMEOUT)
    assert all(active for minute, active in trace if 13.2 <= minute <= 63.9)
    assert not trace[-1][1]


def test_power_on_dip_is_ignored():
    tracker = TemSenStepTracker()
    run(tracker, [(10, 22)], COOL, COOL_TIMEOUT)
    tracker.power_on(T0 + timedelta(minutes=10))
    trace = run(tracker, [(20, 21)], COOL, COOL_TIMEOUT, start=T0 + timedelta(minutes=10))
    assert active_minutes(trace) == 0
    trace = run(tracker, [(10, 20)], COOL, COOL_TIMEOUT, start=T0 + timedelta(minutes=30))
    assert trace[-1][1] is True


def test_missing_reading_keeps_state():
    tracker = TemSenStepTracker()
    run(tracker, [(10, 20), (5, 21)], HEAT, HEAT_TIMEOUT)
    assert tracker.update(None, HEAT, HEAT_TIMEOUT, T0 + timedelta(minutes=16)) is True
