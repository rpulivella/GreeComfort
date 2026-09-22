# GreeComfort

Committed on purpose: the always-loaded law. The gate for what belongs here is **"will I need
this in every session?"** It carries the concepts and the invisible laws you reason from, and it
**never restates what the code, the manifest or a README already owns** (an entity list, a line
count, a version, a dependency), because a copy goes stale and then gets trusted. Anything
procedural (commit, draft a PR, review, merge, tag a release) belongs to a **skill** in
`.claude/commands/`. Machine-specific facts, such as where the live Home Assistant is deployed,
live in the git-ignored `CLAUDE.local.md` and never in this file.

**References name one thing.** A pull request is `PR #38`, never a bare number or a bare `#`.
GreeComfort has no ticket system.

## What GreeComfort is

A Home Assistant custom integration for Gree air conditioners, forked from
[RobHofmann/HomeAssistant-GreeClimateComponent](https://github.com/RobHofmann/HomeAssistant-GreeClimateComponent)
at 3.3.2 and licensed GPL-3.0 because of it (`NOTICE` carries the attribution). Its own domain,
`gree_comfort`, runs beside the core `gree` integration. It adds comfort presets with separate heat
and cool temperatures, manual override tracking, smart 8°C frost protection and Eco Shutoff. One
developer, through an agentic harness, and one live unit that every change is eventually tested on.

## Build and gates

```bash
.venv/bin/python3 scripts/pr-preflight-check.py   # every gate, what CI runs
.venv/bin/python3 -m pytest tests -k eco           # a subset while working
```

The venv pins the test harness to the Home Assistant release in use (`requirements_test.txt`).
CI runs `preflight` and `hassfest`, and only on a pull request that has left draft.

## Laws you cannot learn from the code

### Units

- **Every temperature is native °C inside the integration, and Home Assistant converts.** The
  climate entity reports `temperature_unit = °C`; numbers and sensors declare a temperature device
  class with a °C native unit; a service call arrives already converted to °C. Never hold, compare
  or restore a value in the display unit. Comparing a °F setpoint with a °C sensor is how Eco
  Shutoff never fired in heat and always fired in cool.
- **Differences are `temperature_delta`, never `temperature`.** A 2.5 °C margin is 4.5 °F, not
  36.5 °F. HA does not pick a display unit for a delta number, so those report in the system unit
  and convert with `TemperatureDeltaConverter`.
- **Unit logic outside HA's converters lives only at the device protocol boundary.**
  `_encode_setpoint` and `_decode_setpoint_c` are the pair: with a °F system a setpoint goes to the
  unit as whole °F through `gree_f_to_c`, so the unit's own display matches HA. Nothing else in the
  integration knows the system unit.
- **An external sensor is converted from its declared unit with `TemperatureConverter`**, K
  included. A sensor without a temperature unit is refused, never assumed to be °C.

### The unit tells us almost nothing

- **The protocol reports no compressor state.** `Pow` is power, not running. `hvac_action` is
  inferred from the unit's own `TemSen` reading, which is whole °C and sits one step toward the
  conditioned direction while the compressor runs. A reading counts after it holds 3 minutes; a
  step toward the mode's direction means running, a step back means idle, and a run times out (35
  minutes heat, 60 cool). Power-on dips are ignored for 6 minutes. The thresholds are measured
  from live history, not chosen; change them only against new data.
- **`TemSen` is not the room temperature for decisions.** It sits at the head of the unit and
  moves with airflow. Eco Shutoff decides from the user's external sensor, and goes dark safely
  when that sensor is missing or stale.
- **A command is sent whole.** `SyncState` reads the unit, applies the change, and
  `SendStateToAc` sends every option, so a send never carries a stale value.

### State that must stay consistent

- **Every save goes through `_save_persistent_state()`**, never `_storage.async_save()` directly,
  so the stored dict is always complete.
- **Eco Shutoff owns a power-off it caused.** While it holds the unit off, the entity keeps its real
  mode and reports `idle`, so re-engage can run. Any explicit setpoint change hands control back
  and restores power. The satisfied side is a dwell; the re-engage side is immediate.
- **Smart 8°C (`StHt`) belongs to heat.** Leaving heat clears it in the same command as the mode
  change, never a poll later.
- **Manual override compares exact device encodings** (`SetTem`/`TemRec`), never temperatures with
  a tolerance, so rounding can never flag an override.
- **Unique IDs and restored states are a contract with every installation.** A renamed entity key
  needs a registry migration; a changed stored format needs a one-time migration that reads what
  the old version wrote. This is the one place backward compatibility is required.

### Home Assistant compliance

- **`hassfest` is the authority on structure.** Translations nest entity strings under the entity's
  `translation_key` and carry no `description`; `icons.json` never repeats a default; every
  component the code imports is a manifest dependency. Run it before a PR touches any of those.
- **HACS distributes GreeComfort**: one integration per repository, brand images in the
  integration's `brand/` folder, and a manifest carrying every key HACS requires.

## The shape of a change

- **Choose the simplest implementation that fully meets the requirement, and decide for the long
  term.** No speculative configuration or indirection, and no stopgap.
- **Understand the owning path before editing**: entity, `SyncState`, the protocol, persistence and
  the dispatcher signal that updates dependent entities.
- **One implementation per operation.** A conversion, an encoding or a threshold written twice is a
  rule with two answers.
- **Remove what is dead** in the commit that made it dead: unused state, obsolete flags, temporary
  diagnostics.
- **Never swallow a failure where it changes the outcome.** Log it, surface a repair issue when the
  user must act, and leave the unit in a safe state.

## Tests

- **The simulated unit answers at `FetchResult`**, so request building, encryption, `SyncState` and
  `SendStateToAc` run for real. Mock nothing above it.
- **Go through Home Assistant**: load the integration with `MockConfigEntry` and act through
  service calls, so HA's own conversion, validation and restore are exercised.
- **Every bug fix carries a regression test that fails against the original defect**, and a new
  test is checked to fail with the fix removed.
- **One test, one behavior**, named for it, with a parameterized matrix for boundaries.
- **Live testing is the user's**, on the real unit. Never claim live behavior from a test.

## Comments and prose

- **Comments are one line and say why.** Never narrate code, restate a name, describe the change
  being made, or comment code out.
- US English, no contractions, no em dashes, in code, commits and documents alike.

## Workflow laws

- **Commit only with explicit approval, every time.** `/commit` carries the format.
- **Every pull request stands alone**, opens as a draft, and leaves draft only through
  `/pr-review-code`. Branches and pull requests are never stacked.
- **Merges are real merge commits**, so every commit is permanent and granularity matters: at least
  one commit per logical change, every commit's preflight green.
- **Never deploy to a live Home Assistant without the user's explicit consent** for that deploy,
  given in the terminal. Deploy details are in `CLAUDE.local.md`.
- **What never enters the repository**: tokens, the deploy location, host names, addresses, anything
  that identifies the house the integration runs in.

## Skills pull the right context at the right moment

Ours live in `.claude/commands/`, named `[topic]-[verb]`: `/commit`, `/pr-draft`,
`/pr-review-code`, `/pr-merge`, `/release-tag`. `CONTRIBUTING.md` is the human-readable version of
the same workflow.
