# Gree Comfort Integration - Implementation Documentation

Custom fork of [HomeAssistant-GreeClimateComponent](https://github.com/RobHofmann/HomeAssistant-GreeClimateComponent) v3.3.2

## Overview

This implementation extends the base Gree integration with comprehensive comfort management features:

- **Comfort Preset Modes**: Home, Sleep, Away, Off with dual heat/cool temperatures
- **Number Entities**: User-configurable preset temperatures and feature settings
- **Manual Override Tracking**: Binary sensor detects manual temperature adjustments
- **Clear Override Button**: One-tap return to preset temperature
- **Cycle Management**: Optional compressor protection with configurable timing
- **HVAC Action Tracking**: Real-time state reporting (heating/cooling/idle/drying/fan/off)
- **Native Temperature Units**: Entities report °C; Home Assistant converts to the user's unit system
- **Full Persistence**: All settings survive restarts via RestoreNumber and RestoreEntity

## Key Design Decisions

### Domain Separation
- **Domain**: `gree_comfort` (not `gree`)
- **Why**: Avoids conflicts with HACS version, allows side-by-side testing
- **Impact**: Users must fully remove HACS version before installing

### Temperature Configuration via Number Entities
- **Choice**: Preset temperatures are number entities on device page, NOT in config dialog
- **Why**:
  - Easier user access (no config dialog navigation)
  - Automation-friendly (can set temps programmatically)
  - Persistent via RestoreNumber, which records each value's unit
  - Follows HA best practices for user-adjustable values
- **Impact**: Config dialog only has original options + cycle management

### Temperature Storage Strategy
- **Internal**: All temperatures stored in Celsius, the device's unit
- **Display**: Entities report native °C and Home Assistant converts; the integration does no display conversion
- **Absolute temps**: `device_class` temperature on climate, preset numbers and sensors
- **Delta temps** (Eco Shutoff margins): `device_class` temperature_delta, reported in the system unit via `TemperatureDeltaConverter`
- **Setpoint encoding**: With a °F system, setpoints go to the unit as whole °F (`gree_f_to_c`), the only unit logic outside Home Assistant
- **Why**: Hand conversion in several places once compared a °F setpoint against a °C sensor

### Manual Override Behavior
- **Detection**: Any manual temperature change while preset is active sets override flag
- **Persistence**: Override flag persists across restarts
- **Clear**: Either press button OR change preset mode
- **Signal**: Uses dispatcher pattern for real-time binary sensor updates
- **Why**: Allows users to temporarily adjust without losing preset mode

### Preset Temperature Logic
Each preset stores **two temperatures**: one for heat mode, one for cool mode.

**Example Flow:**
```
User: Set Away preset
  → If HVAC mode = Heat → Apply away_heat (59°F/15°C)
  → If HVAC mode = Cool → Apply away_cool (82°F/28°C)

User: Change HVAC mode from Heat to Cool (while Away preset active)
  → Automatically switches from away_heat to away_cool

User: Manually adjust temperature
  → Manual override flag turns ON
  → Temperature stays at manual value
  → Preset mode still shows "Away" but doesn't control temp

User: Press "Clear Manual Override" button
  → Reapplies away_cool (current preset + HVAC mode)
  → Manual override flag turns OFF
```

## Files Modified/Created

### Core Climate Entity
**File**: `custom_components/gree_comfort/climate.py`

**Added**:
- Preset mode constants and support flags
- `_preset_mode`, `_preset_temps` state variables
- `_manual_override` flag and `_applying_preset` flag
- Number entity references for preset temps
- `preset_mode`, `preset_modes`, `hvac_action` properties
- `async_set_preset_mode()` service method
- `_apply_preset_temperature()` helper method
- `async_clear_manual_override()` method
- `_set_manual_override()` helper with dispatcher signal
- Enhanced `async_set_temperature()` to detect manual changes
- Enhanced `async_set_hvac_mode()` to apply preset temps
- Enhanced `extra_state_attributes` with rounded preset temps
- Cycle management logic in `_manage_temperature_cycling()`
- HVAC action inferred from settled `TemSen` steps (`TemSenStepTracker` in `helpers.py`)

**Modified**:
- Imports: Added `async_dispatcher_send`, number/binary_sensor/button descriptions
- `__init__`: Load preset temps from number entities

### Number Entities
**File**: `custom_components/gree_comfort/number.py`

**Features**:
- Number entity descriptions for 6 preset temps, Eco Shutoff tuning and the smart 8°C threshold
- Native °C with temperature device classes; Home Assistant converts for display
- Temperature-delta device class for Eco Shutoff margins
- RestoreNumber persistence; values saved before 1.1.0 migrate once using their recorded unit
- EntityCategory.CONFIG for proper UI placement
- Custom value setters that update climate entity

**Entities Created**:
1. `preset_home_heat` - Home preset heating temperature
2. `preset_home_cool` - Home preset cooling temperature
3. `preset_sleep_heat` - Sleep preset heating temperature
4. `preset_sleep_cool` - Sleep preset cooling temperature
5. `preset_away_heat` - Away preset heating temperature
6. `preset_away_cool` - Away preset cooling temperature

### Binary Sensor
**File**: `custom_components/gree_comfort/binary_sensor.py`

**Features**:
- Manual override binary sensor
- Dispatcher signal listener for real-time updates
- Updates immediately when climate entity sets override flag
- Signal format: `{DOMAIN}_{mac_addr}_manual_override_update`

### Button Entity
**File**: `custom_components/gree_comfort/button.py`

**Created**: Button entity for clearing manual override
- Calls `device.async_clear_manual_override()`
- Icon: `mdi:restore`
- Only shows when manual override is active (via conditional cards)

### Select Entities
**File**: `custom_components/gree_comfort/select.py`

**Features**:
- External temperature sensor selection (existing)
- **Comfort Mode select** (new) - Quick access to preset modes for dashboard tiles

**Comfort Mode Select**:
- Options: Home, Sleep, Away, Off (excludes "None" internal state)
- Two-way sync with climate entity via dispatcher signals
- Icon: `mdi:home-thermometer`
- When user selects option → calls `climate.async_set_preset_mode()`
- When climate preset changes → select entity updates via dispatcher signal
- Signal format: `{DOMAIN}_{mac_addr}_preset_mode_update`
- Perfect for custom dashboard cards (mushroom, button cards, etc.)

**Use Case**: Provides cleaner UI for dashboard tiles compared to using climate entity preset attribute.

### Configuration Flow
**File**: `custom_components/gree_comfort/config_flow.py`

**Modified**:
- Removed `__init__` from OptionsFlowHandler (HA 2026.x compatibility)
- Removed preset temperature options (now handled by number entities)
- Removed idle tolerance option (idle is inferred from TemSen steps)
- Kept original options: HVAC modes, fan modes, swing modes, etc.
- Added cycle management options:
  - `enforce_off_cycle` (boolean)
  - `min_off_time_seconds` (0-360, default 180)
  - `min_cycle_duration_seconds` (0-600, default 300)

### Constants
**File**: `custom_components/gree_comfort/const.py`

**Added**:
- Cycle management config keys
- Option keys set for validation

### Base Entity
**File**: `custom_components/gree_comfort/entity.py`

**Modified**:
- Added `GreeEntityDescription` base class
- Added `GreeEntity` base class with common properties
- Value function and availability function support

### Integration Setup
**File**: `custom_components/gree_comfort/__init__.py`

**Modified**:
- Added `Platform.BUTTON` to platforms list
- Creates device instance in `async_setup_entry()`
- Stores device for access by all platform entities

### Manifest
**File**: `custom_components/gree_comfort/manifest.json`

**Modified**:
- Domain: `gree_comfort`
- Name: `Gree Comfort`
- Version: `3.3.2-comfort`
- Removed documentation link (no GitHub repo yet)
- Cleared codeowners

### Translations
**File**: `custom_components/gree_comfort/translations/en.json`

**Added**:
- Number entity translations (names, descriptions)
- Binary sensor translation (manual override)
- Button translation (clear override)
- Config dialog cycle management options
- Removed all non-English translations for maintainability

## Implementation Details

### HVAC Action State Logic

```python
def hvac_action(self):
    if not self._acOptions or self._acOptions.get('Pow') == 0:
        return HVACAction.OFF

    mode = self.hvac_mode

    if mode == HVACMode.DRY:
        return HVACAction.DRYING
    elif mode == HVACMode.FAN_ONLY:
        return HVACAction.FAN

    if mode == HVACMode.HEAT and self._temsen_active:
        return HVACAction.HEATING
    if mode == HVACMode.COOL and self._temsen_active:
        return HVACAction.COOLING
    return HVACAction.IDLE
```

`_temsen_active` comes from `TemSenStepTracker`, fed every poll with the raw °C `TemSen` reading. A reading settles after holding 3 minutes; a settled step toward the mode's direction marks the unit running until a step back or a timeout (35 minutes heat, 60 minutes cool). Mode changes re-baseline the tracker, and readings within 6 minutes of power-on are ignored. The thresholds come from TemSen, aux sensor and eco history from February to September 2026.

### Manual Override Detection

```python
async def async_set_temperature(self, **kwargs):
    # Existing temperature setting logic...

    # Detect manual override (unless applying preset)
    if not getattr(self, '_applying_preset', False):
        self._set_manual_override(True)

def _set_manual_override(self, value: bool):
    self._manual_override = value
    # Send dispatcher signal for binary sensor
    signal = f"{DOMAIN}_{self._mac_addr}_manual_override_update"
    async_dispatcher_send(self.hass, signal, value)
```

### Preset Temperature Application

```python
async def _apply_preset_temperature(self):
    if self._preset_mode in (PRESET_NONE, PRESET_OFF):
        return

    # Get temperatures for current preset
    temps = self._preset_temps[self._preset_mode]

    # Select temp based on HVAC mode
    if self.hvac_mode == HVACMode.HEAT:
        target = temps["heat"]
    elif self.hvac_mode == HVACMode.COOL:
        target = temps["cool"]
    else:
        return  # No temp for dry/fan modes

    # Apply without triggering manual override
    self._applying_preset = True
    await self.async_set_temperature(temperature=target)
    self._applying_preset = False

    # Clear manual override when preset changes
    self._set_manual_override(False)
```

### Temperature Conversion

Conversion uses Home Assistant's converters rather than local formulas:

```python
from homeassistant.util.unit_conversion import TemperatureConverter, TemperatureDeltaConverter

TemperatureConverter.convert(value, from_unit, UnitOfTemperature.CELSIUS)       # absolute, with offset
TemperatureDeltaConverter.convert(value, from_unit, UnitOfTemperature.CELSIUS)  # delta, no offset
```

### Cycle Management

```python
async def _manage_temperature_cycling(self):
    """Enforce minimum on/off times for compressor protection."""
    if not self._enforce_cycle:
        return

    now = datetime.now()
    is_on = self._acOptions.get('Pow', 0) == 1

    if is_on:
        # Check minimum off time before allowing turn on
        if self._last_off_time:
            off_duration = (now - self._last_off_time).total_seconds()
            if off_duration < self._min_off_time:
                # Too soon, delay turn on
                return
    else:
        # Check minimum cycle duration before allowing turn off
        if self._last_on_time:
            on_duration = (now - self._last_on_time).total_seconds()
            if on_duration < self._min_cycle_duration:
                # Too soon, delay turn off
                return

    # Update timestamps
    if is_on and not self._was_on:
        self._last_on_time = now
    elif not is_on and self._was_on:
        self._last_off_time = now

    self._was_on = is_on
```

### Number Entity Persistence

```python
class GreeNumber(GreeEntity, NumberEntity, RestoreEntity):
    async def async_added_to_hass(self):
        await super().async_added_to_hass()

        if self.entity_description.restore_state:
            # Restore last value
            last_state = await self.async_get_last_number_data()
            if last_state and last_state.native_value is not None:
                self._attr_native_value = last_state.native_value
            else:
                # Use default from device
                self._attr_native_value = self.entity_description.value_fn(self._device)
```

## Testing Results

### Unit Conversion
✅ Fahrenheit display correct (80°F → 26.67°C → 80°F)
✅ Celsius display correct (20°C stays 20°C)
✅ Delta conversion correct (1°C = 1.8°F, not 33.8°F)
✅ No rounding drift

### Manual Override
✅ Triggers on manual temp change
✅ Persists across restarts
✅ Binary sensor updates in real-time
✅ Clear button works
✅ Doesn't trigger when applying presets

### Preset Modes
✅ Home/Sleep/Away apply correct temps
✅ Heat/Cool mode switch applies correct temps
✅ OFF preset turns unit off
✅ Preset persists across restarts

### HVAC Action
✅ Reports HEATING after a settled TemSen step up in heat
✅ Reports COOLING after a settled TemSen step down in cool
✅ Reports IDLE after a step back or the run timeout
✅ Reports DRYING in dry mode
✅ Reports FAN in fan mode
✅ Reports OFF when powered off

### Cycle Management
✅ Enforces minimum off time
✅ Enforces minimum cycle duration
✅ Configurable via options dialog
✅ Can be disabled

## Installation

1. **Remove HACS Gree integration** (if installed):
   ```
   HACS → Integrations → Gree Climate → Remove
   Settings → Devices & Services → Gree Climate → Delete
   ```

2. **Install Gree Comfort**:
   ```bash
   ./install.sh /path/to/homeassistant/config
   ```
   Or manually:
   ```bash
   cp -r custom_components/gree_comfort /config/custom_components/
   ```

3. **Restart Home Assistant**

4. **Add integration**:
   ```
   Settings → Devices & Services → Add Integration → Gree Comfort
   ```

5. **Configure number entities**:
   ```
   Settings → Devices & Services → Gree Comfort → [Device] → Number entities
   ```

## Upgrade Path from Base Integration

If upgrading from the base Gree integration:

1. Note your current device settings (IP, MAC, etc.)
2. Remove base Gree integration completely
3. Install Gree Comfort
4. Add device using noted settings
5. Configure preset temperatures via number entities
6. Set up automations for preset modes

**Note**: Cannot run both integrations simultaneously due to device conflicts.

## Future Enhancements (Not Implemented)

- **External temperature sensor**: Already supported via select entity
- **Multi-zone support**: Would require significant refactoring
- **Learning mode**: Could track manual changes and suggest preset temps
- **Schedule integration**: Use HA automations instead
- **Energy monitoring**: Would need device support

## Known Limitations

1. **Device capability dependent**: Some features (humidity, outside temp) require device support
2. **Network dependent**: Available check can be disabled for unreliable networks
3. **Encryption versions**: Auto-detection may fail on some models, manual config needed
4. **Single unit per integration entry**: Multi-split systems need separate entries

## Version History

- **3.3.2-comfort** (2026-02-01): Initial comfort mode implementation
  - Preset modes with dual temperatures
  - Number entities for configuration
  - Manual override tracking
  - Cycle management
  - HVAC action tracking
  - Temperature delta conversion

- **3.3.2** (base): Upstream version from RobHofmann
  - Basic climate control
  - HVAC modes
  - Fan modes
  - Swing modes
  - Device discovery

## References

- Upstream: https://github.com/RobHofmann/HomeAssistant-GreeClimateComponent
- Home Assistant Climate: https://developers.home-assistant.io/docs/core/entity/climate
- Home Assistant Number: https://developers.home-assistant.io/docs/core/entity/number
- RestoreEntity: https://developers.home-assistant.io/docs/core/entity#restoreentity
