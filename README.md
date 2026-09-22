# Gree Comfort

[![HACS: custom repository](https://img.shields.io/badge/HACS-custom%20repository-41BDF5.svg)](https://hacs.xyz/docs/faq/custom_repositories)
[![Release](https://img.shields.io/github/v/release/rpulivella/GreeComfort)](https://github.com/rpulivella/GreeComfort/releases)
[![License: GPL-3.0](https://img.shields.io/badge/license-GPL--3.0-blue.svg)](LICENSE)

A Home Assistant integration for Gree air conditioners that adds comfort presets, tracks when
someone overrides them, and turns the unit off once the room is genuinely comfortable.

It talks to the unit directly over your own network, with no cloud account and no Gree app.

## Features

A Gree air conditioner knows one target temperature and nothing else. Gree Comfort keeps the
house's intentions on the Home Assistant side and leaves the unit to do what it does best.

- **Comfort presets.** Home, Sleep and Away each hold their own heating and cooling
  temperature, so a schedule or an automation switches intent rather than numbers. Changing the
  mode applies the right one of the pair.
- **Manual override tracking.** When someone changes the temperature by hand, a binary sensor
  says so, and a button puts the preset back. Automations can tell "the house decided this" from
  "a person decided this", which is what makes an override watchdog possible.
- **Eco Shutoff.** When the room has stayed comfortably past the setpoint for a while, the unit
  is powered off rather than left cycling, and powered back on when the room drifts back. The
  decision uses a room sensor you choose, never the unit's own.
- **Smart 8°C.** After a chosen time in Sleep or Away while heating, the unit's built-in 8°C
  frost protection engages, and it is cleared the moment the mode changes.
- **Real heating and cooling status.** `hvac_action` reports what the compressor is actually
  doing, inferred from the unit's own sensor, so energy dashboards and history mean something.
- **Everything is an entity.** Preset temperatures, Eco Shutoff tuning and the device's own
  features (X-fan, lights, quiet, turbo, health, power save) are numbers, switches and selects on
  the device page, so automations can reach all of them.

## Design

Three facts about these units shape the whole design.

- **The unit reports no compressor state.** Its protocol says whether power is on, not whether it
  is heating. Gree Comfort infers activity from the unit's own temperature sensor, which moves one
  whole degree Celsius toward the direction it is conditioning while the compressor runs, and back
  when it stops. A reading counts only after it holds for three minutes, which filters the flicker,
  and a run times out if nothing further happens.
- **The unit's own sensor sits in the head, not the room.** It reads the air at the appliance and
  moves with the fan, so it is fine for detecting activity and wrong for deciding comfort. Eco
  Shutoff therefore requires an external sensor, and if that sensor goes missing or stale it
  restores power and raises a repair issue rather than guessing.
- **The unit takes whole degrees.** Setpoints are encoded at the protocol boundary, so what Home
  Assistant shows and what the unit's own display shows agree. Everything inside the integration
  is Celsius, and Home Assistant converts for you.

## Requirements

- Home Assistant **2026.8** or newer.
- A Gree air conditioner (or a unit using Gree's protocol, sold under many brands) reachable on
  your network. Both encryption generations are supported and detected during setup.
- For Eco Shutoff, a temperature sensor in the room. Any Home Assistant temperature sensor works.

## Installation

### HACS

1. In Home Assistant, open **HACS**.
2. Open the three-dot menu and choose **Custom repositories**.
3. Add `https://github.com/rpulivella/GreeComfort` with the type **Integration**.
4. Search HACS for **Gree Comfort** and download it.
5. Restart Home Assistant.

### Manual install

1. Copy `custom_components/gree_comfort/` from the latest release into your Home Assistant
   configuration folder, so it lands at `config/custom_components/gree_comfort/`.
2. Restart Home Assistant.

### Configuration

1. Go to **Settings → Devices & Services → Add Integration** and choose **Gree Comfort**.
2. Let it scan your network, or enter the unit's IP and MAC address yourself.
3. The encryption generation is detected for you.
4. Set the preset temperatures on the device page, and choose an Eco Shutoff sensor if you want
   that feature.

Gree Comfort uses its own `gree_comfort` domain, so it can run alongside Home Assistant's
built-in `gree` integration on the same system.

## Feature reference

### Presets

Each preset holds two temperatures, one for heating and one for cooling. Switching preset or mode
applies the matching one. `Off` turns the unit off.

### Manual override

Any temperature change that did not come from a preset sets the override flag, and the binary
sensor reflects it immediately. The **Clear manual override** button reapplies the current
preset's temperature. A preset change clears it too.

### Eco Shutoff

Off by default. Once enabled and given a sensor, it powers the unit off after the room has stayed
past the setpoint by the satisfied margin, continuously, for the dwell window. It powers back on
as soon as the room comes back within the re-engage delta of the setpoint. While it holds the unit
off, the entity keeps its real mode and reports `idle`, and any setpoint change hands control back
to you at once.

### Smart 8°C

Off by default. In Sleep or Away while heating, it engages the unit's own 8°C frost protection
after the configured time. Leaving heat clears it in the same command as the mode change. The
manual 8°C switch keeps working on its own.

## Entities

| Platform | What you get |
|---|---|
| `climate` | The unit: mode, target temperature, fan, swing, presets and `hvac_action` |
| `number` | Six preset temperatures, Eco Shutoff tuning, the smart 8°C threshold, the temperature step |
| `select` | The Eco Shutoff room sensor, and the comfort preset |
| `switch` | Eco Shutoff, smart 8°C, and the unit's own features (X-fan, lights, health, quiet, turbo, power save, sleep, fresh air) |
| `binary_sensor` | Manual override, and whether Eco Shutoff is holding the unit off |
| `button` | Clear manual override |
| `sensor` | Outside temperature, room humidity, the Eco Shutoff sensor reading, and raw device values |

## Troubleshooting

- **The unit shows as unavailable.** It answers on UDP port 7000, so check that Home Assistant and
  the unit are on the same network and that nothing blocks that port. A unit that briefly stops
  answering is retried with backoff.
- **Eco Shutoff never fires.** It needs its switch on, a room sensor chosen, a preset other than
  Off, and the room past the satisfied margin for the whole dwell window.
- **A repair issue about the Eco Shutoff sensor.** The sensor has been unavailable, or has not
  reported for two hours. Power is restored while that lasts, and the issue clears itself when the
  sensor comes back.
- **`hvac_action` looks slow.** It is, by three minutes or so on each edge, which is the price of
  ignoring sensor flicker.

## Development

`CONTRIBUTING.md` carries the workflow: commits, branches, pull requests, merges and releases.

```bash
uv venv -p 3.14 .venv
VIRTUAL_ENV=.venv uv pip install -r requirements_test.txt
.venv/bin/python3 scripts/pr-preflight-check.py   # every gate, what CI runs
```

The test suite runs Home Assistant itself, with a simulated unit answering at the network
boundary, so request building, encryption and the polling loop are all exercised.

## Repository layout

```
custom_components/gree_comfort/   the integration
  brand/                          icon and logo Home Assistant serves
  translations/                   strings
docs/                             design notes and implementation history
scripts/                          the preflight CI runs
tests/                            pytest suite
```

## Credits

Built on [RobHofmann/HomeAssistant-GreeClimateComponent](https://github.com/RobHofmann/HomeAssistant-GreeClimateComponent),
starting from its 3.3.2 release, the source of the device protocol work. Rob Hofmann
and that project's contributors did the hard part of speaking to these units, and the same GPL-3.0
license carries forward here.

Gree Comfort is not affiliated with, endorsed by, or supported by Gree Electric Appliances. It is
developed against one unit in one house, so reports from other models are welcome.

## License

[GPL-3.0](LICENSE), inherited from the upstream integration. See [`NOTICE`](NOTICE) for the origin
and modification notice.
