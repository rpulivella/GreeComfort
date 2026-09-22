# Gree Comfort Integration - Custom Version

**Enhanced Gree integration with comfort modes, cycle management, and manual override tracking.**

## What is Different?

This version extends the base Gree integration with:
- ✅ **Comfort Preset Modes**: Home, Sleep, Away, Off with dual temperatures
- ✅ **Number Entities**: Easy access to preset temperatures on device page
- ✅ **Manual Override Tracking**: Binary sensor shows when temperature is manually adjusted
- ✅ **Clear Override Button**: One-tap return to preset temperature
- ✅ **Smart 8°C Mode**: Auto frost protection for Away/Sleep heat presets after configurable threshold (default 60 min)
- ✅ **Cycle Management**: Optional compressor protection with configurable on/off times
- ✅ **HVAC Action Tracking**: Real-time heating/cooling/idle/drying/fan/off status
- ✅ **Native Temperature Units**: Reports °C and Home Assistant converts to your unit system, including temperature deltas
- ✅ **Full Persistence**: All settings survive restarts

## Based On

- **Upstream**: [RobHofmann/HomeAssistant-GreeClimateComponent](https://github.com/RobHofmann/HomeAssistant-GreeClimateComponent)
- **Base Version**: 3.3.2
- **Domain**: `gree_comfort` (separate from HACS version to avoid conflicts)
- **Language**: English only (simplified for easier maintenance)

## Installation

1. **Remove HACS Gree integration** (if installed):
   ```
   HACS → Integrations → Gree Climate → Remove
   Settings → Devices & Services → Gree Climate → Delete
   ```

2. **Copy custom integration**:
   ```bash
   cp -r custom_components/gree_comfort /config/custom_components/
   ```

3. **Restart Home Assistant**

4. **Add integration**:
   ```
   Settings → Devices & Services → Add Integration → Gree Comfort
   ```

## Entities Created

For each Gree device, the integration creates:

### Climate Entity
- Main climate control with preset modes (Home, Sleep, Away, Off)
- HVAC modes, fan speeds, swing modes
- HVAC action tracking (heating/cooling/idle/etc.)

### Number Entities (8)
- **Preset Home - Heat Temperature**: Target temp for Home preset in heating mode
- **Preset Home - Cool Temperature**: Target temp for Home preset in cooling mode
- **Preset Sleep - Heat Temperature**: Target temp for Sleep preset in heating mode
- **Preset Sleep - Cool Temperature**: Target temp for Sleep preset in cooling mode
- **Preset Away - Heat Temperature**: Target temp for Away preset in heating mode
- **Preset Away - Cool Temperature**: Target temp for Away preset in cooling mode
- **Smart 8°C Threshold**: Minutes Away/Sleep+heat must be active before frost protection engages (default: 60, range: 15–480)

All temperature entities automatically display in your system's preferred units (°F or °C).

### Binary Sensor
- **Manual Override**: Indicates when temperature has been manually adjusted away from preset setting

### Button
- **Clear Manual Override**: Reapplies the current preset temperature and clears manual override flag

### Sensors
- Outside Temperature (if supported by device)
- Room Humidity (if supported by device)
- Power State, Device Mode, Target Temp (Raw), Fan Speed (Raw), Turbo Mode, Quiet Mode, Power Save State

### Switches
- X-Fan, Lights, Health, Power Save, 8°C Heat, Sleep, Air
- Auto X-Fan, Auto Light, Anti Direct Blow, Light Sensor, Beeper
- **Smart 8°C Mode** (config): Enables/disables automatic frost protection for Away/Sleep presets

### Select Entities (2)
- **Comfort Mode**: Quick access to preset modes (Home, Sleep, Away, Off) - perfect for dashboard tiles
- **External Temperature Sensor**: Choose alternative sensor for temperature readings

## Configuration

### Initial Setup

During setup, you can choose:
- **Automatic Discovery**: Scans network for Gree devices
- **Manual Entry**: Specify IP, MAC, port, encryption details

### Options Dialog

After setup, configure via:
```
Settings → Devices & Services → Gree Comfort → Configure
```

**Original Options:**
- HVAC Modes (which modes to show)
- Fan Modes (which fan speeds to show)
- Vertical Swing Modes
- Horizontal Swing Modes
- Disable Available Check (keep entity available even when device unreachable)
- Temperature Sensor Offset (use external sensor instead of built-in)

**Comfort Mode Options:**
- Enforce Cycle Management (protect compressor)
- Minimum Off Time (seconds) - Default: 180
- Minimum Cycle Duration (seconds) - Default: 300

### Preset Temperature Configuration

Preset temperatures are configured via **number entities on the device page**, not in the options dialog. This provides:
- Easy access without entering config dialog
- Automation support (set temperatures programmatically)
- Persistent storage that survives restarts

Access them at:
```
Settings → Devices & Services → Gree Comfort → [Your Device] → See all entities
```

Look for entities like `number.bedroom_ac_preset_home_heat`.

## Usage

### Setting Comfort Modes

**Via UI:**
1. Open your climate card
2. Select preset: Home, Sleep, Away, or Off

**Via Service Call:**
```yaml
service: climate.set_preset_mode
target:
  entity_id: climate.bedroom_ac
data:
  preset_mode: sleep
```

When you select a preset, the integration automatically:
- Sets the appropriate temperature based on current HVAC mode (heat/cool)
- Clears any manual override
- Updates HVAC action based on current vs target temperature

### Comfort Mode in Dashboard Tiles

The **Comfort Mode select entity** (`select.<device>_comfort_mode`) provides a clean way to control presets from dashboard cards:

**Mushroom Entity Card:**
```yaml
type: custom:mushroom-entity-card
entity: select.bedroom_ac_comfort_mode
icon: mdi:home-thermometer
name: Comfort Mode
fill_container: false
layout: horizontal
```

**Standard Entities Card:**
```yaml
type: entities
entities:
  - entity: select.bedroom_ac_comfort_mode
    name: Bedroom Comfort
```

**Button Card:**
```yaml
type: button
entity: select.bedroom_ac_comfort_mode
icon: mdi:home-thermometer
show_state: true
```

The select entity syncs automatically with the climate entity's preset mode - change one and the other updates instantly.

### Adjusting Preset Temperatures

**Via UI:**
```
Settings → Devices & Services → Gree Comfort → [Device] →
number.bedroom_ac_preset_home_heat → Set value
```

**Via Service Call:**
```yaml
service: number.set_value
target:
  entity_id: number.bedroom_ac_preset_home_heat
data:
  value: 70  # in your system's units (°F or °C)
```

### Manual Override Behavior

When you manually adjust temperature while a preset is active:
- Binary sensor `binary_sensor.bedroom_ac_manual_override` turns **on**
- Climate card shows your manual temperature
- Preset mode remains selected but is not actively controlling temperature

To return to preset control:
- Press the "Clear Manual Override" button, OR
- Change to a different preset mode

**Example Automation Card:**
```yaml
type: custom:mushroom-template-card
primary: Tap to Resume
secondary: "{{ entity | device_id | device_attr('name') }} manual override"
icon: mdi:restart
entity: button.bedroom_ac_clear_manual_override
visibility:
  - condition: state
    entity: binary_sensor.bedroom_ac_manual_override
    state: "on"
color: red
tap_action:
  action: toggle
```

### HVAC Action Detection

The unit does not report whether its compressor is running, so the integration infers it from the unit's own temperature sensor (`TemSen`). That sensor reads in whole °C and, while the unit runs, sits one step toward the conditioned direction, stepping back when the run ends.

- A new reading counts only after it holds for 3 minutes, which filters flicker between two adjacent values
- In heat, a settled step up means `heating` and a step down means `idle`; in cool, a step down means `cooling` and a step up means `idle`
- With no further step, `heating` ends after 35 minutes and `cooling` after 60 minutes; another step in the same direction restarts that time
- Readings in the first 6 minutes after power-on are ignored, because the fan starting moves the sensor on its own
- Off, Eco Shutoff (`idle`), dry and fan modes are reported directly; auto mode reports no action

**Access HVAC Action:**
```yaml
{{ state_attr('climate.bedroom_ac', 'hvac_action') }}
```

Returns: `heating`, `cooling`, `idle`, `drying`, `fan`, or `off`

**Limits:** a room drifting across a 1°C boundary on its own looks like a run start and reads as `heating` or `cooling` until the timeout. Detection lags a real run start by the 3-minute settle time plus however long the sensor takes to step.

### Cycle Management

When enabled, cycle management prevents rapid compressor cycling by enforcing:
- **Minimum Off Time**: Unit must stay off for at least this many seconds before turning on
- **Minimum Cycle Duration**: Unit must stay on for at least this many seconds before turning off

This protects the compressor and reduces wear. Configure in the options dialog:
```
Settings → Devices & Services → Gree Comfort → Configure
```

**Note**: Cycle management only affects automatic preset temperature changes, not manual control.

### Smart 8°C Mode

When Away or Sleep preset is active in **heating mode**, the integration can automatically engage the device's built-in 8°C frost protection (`StHt`) after a configurable time threshold. This is useful when you leave home or go to sleep and want the unit to drop to 8°C/46°F for energy savings once enough time has passed.

**How it works:**
1. You set the preset to Away or Sleep with HVAC mode = Heat
2. A timer starts
3. After the threshold (default 60 min), `StHt=1` is sent to the device
4. The device locks to 8°C (displayed as 8°C or 46°F in HA)
5. When you change preset to Home (or any non-eligible preset), `StHt=0` is sent and the preset temperature is restored

**Configuration (on device page):**
- **Smart 8°C Mode** switch, enable/disable the feature (default: on)
- **Smart 8°C Threshold** number, minutes before activation (default: 60, range: 15–480)

**Manual 8°C Heat switch:**
The existing **8°C Heat** switch on the device page still works independently at any time. If you manually turn it on, it counts as a manual override. If you manually turn it off while smart mode is active, the timer restarts and smart mode will re-engage after the full threshold.

**State attributes for debugging:**
```yaml
{{ state_attr('climate.bedroom_ac', 'stht_smart') }}
# Returns: {active, preset_active_since, elapsed_minutes, threshold_minutes}
```

## Automation Examples

### Adjust Away Temperature When Leaving
```yaml
automation:
  - alias: "Lower heat when away"
    trigger:
      - platform: state
        entity_id: person.user
        to: "not_home"
    action:
      - service: climate.set_preset_mode
        target:
          entity_id: climate.bedroom_ac
        data:
          preset_mode: away
```

### Seasonal Preset Adjustment
```yaml
automation:
  - alias: "Adjust sleep temps for summer"
    trigger:
      - platform: time
        at: "00:00:00"
    condition:
      - condition: template
        value_template: "{{ now().month in [6,7,8] }}"
    action:
      - service: number.set_value
        target:
          entity_id: number.bedroom_ac_preset_sleep_cool
        data:
          value: 68
```

### Alert on Manual Override
```yaml
automation:
  - alias: "Notify when AC manually overridden"
    trigger:
      - platform: state
        entity_id: binary_sensor.bedroom_ac_manual_override
        to: "on"
    action:
      - service: notify.mobile_app
        data:
          message: "AC temperature was manually adjusted"
```

### Auto-clear Override After Time
```yaml
automation:
  - alias: "Clear AC override after 2 hours"
    trigger:
      - platform: state
        entity_id: binary_sensor.bedroom_ac_manual_override
        to: "on"
        for:
          hours: 2
    action:
      - service: button.press
        target:
          entity_id: button.bedroom_ac_clear_manual_override
```

## Temperature Unit Handling

Every temperature is held in °C, the unit the device uses, and Home Assistant converts it to your unit system for display and for service calls.

### Absolute Temperatures
The climate entity, the preset temperature numbers and the temperature sensors report native °C with a temperature device class, so Home Assistant displays them in °F or °C to match your unit system. When your system uses °F, setpoints are sent to the unit as whole °F, so the unit's own display matches Home Assistant.

### Temperature Deltas
The Eco Shutoff satisfied margin and re-engage delta are differences rather than temperatures, and use the temperature-delta device class. They display in your unit system and convert without the +32 offset: a 2.5°C margin shows as 4.5°F, not 36.5°F.

### Changing the Unit System
Saved number values record their unit, so switching between °F and °C converts them instead of misreading them.

## Troubleshooting

### Preset temperatures not applying
1. Check that preset mode is selected (not "Off")
2. Verify HVAC mode is set (heat/cool/auto, not "off")
3. Check manual override binary sensor - if on, press clear override button

### Manual override will not clear
1. Press the "Clear Manual Override" button
2. Or switch to a different preset mode
3. Check logs for errors

### Number entities showing wrong units
1. Verify your HA system unit setting: `Settings → System → General → Unit System`
2. Reload the integration: `Settings → Devices & Services → Gree Comfort → Reload`
3. Number entities should automatically display in your system's units

### Cycle management not working
1. Verify it is enabled in options dialog
2. Check that min times are set appropriately (defaults: 180s off, 300s on)
3. Review logs for cycle management messages

### Smart 8°C mode not activating
1. Verify "Smart 8°C Mode" switch is on (device page → see all entities)
2. Confirm preset is Away or Sleep AND HVAC mode is Heat AND unit is powered on
3. Check `stht_smart.elapsed_minutes` in state attributes to see timer progress
4. Check that threshold is not set too high

## Technical Details

### State Persistence
- Preset temperatures: Stored via RestoreEntity, survive restarts
- Manual override flag: Stored in climate entity, survives restarts
- Preset mode: Stored in climate entity, survives restarts
- Smart 8°C active flag + timer start: Stored in climate entity, survives restarts

### Real-time Updates
- Manual override binary sensor updates immediately via dispatcher signals
- No polling delay between climate entity and binary sensor

### Temperature Storage
- All temperatures stored internally in Celsius
- Conversion happens only at display/input boundaries
- Ensures consistency across restarts and unit changes

## Support

This is a personal modification of the upstream Gree integration.

**For issues with comfort mode features** (presets, manual override, cycle management):
- Check this README
- Review automation/configuration

**For issues with base Gree functionality** (connection, device discovery, basic climate control):
- See [upstream repository](https://github.com/RobHofmann/HomeAssistant-GreeClimateComponent)

## Version History

- **3.3.2-comfort-2** (2026-02-23): Smart 8°C mode; fix 8°C displaying as 8°F in Fahrenheit systems
- **3.3.2-comfort-1** (2026-02-01): Added comfort modes, manual override, cycle management, number entities
- **3.3.2** (base): Upstream version from RobHofmann
