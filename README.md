# Gree Comfort - Custom Home Assistant Integration

Enhanced Gree HVAC integration with comfort modes, manual override tracking, and cycle management.

## Project Structure

```
GreeComfort/
├── custom_components/
│   └── gree_comfort/          # Working integration (ready to install)
├── docs/
│   ├── README.md              # Full feature documentation
│   └── IMPLEMENTATION_PLAN.md # Technical implementation details
└── README.md                  # This file
```

## Quick Start

### Installation

```bash
./install.sh /path/to/homeassistant/config
```

Or manually:
```bash
cp -r custom_components/gree_comfort /config/custom_components/
```

### Add to Home Assistant

1. Restart Home Assistant
2. Go to: Settings → Devices & Services → Add Integration
3. Search for: **Gree Comfort**
4. Follow setup wizard

### Configure

- **Basic settings**: During setup wizard
- **Advanced options**: Settings → Devices & Services → Gree Comfort → Configure
- **Preset temperatures**: Settings → Devices & Services → Gree Comfort → [Device] → Number entities

## Features

- ✅ **Comfort Preset Modes**: Home, Sleep, Away, Off
- ✅ **Dual Temperatures**: Separate heat/cool temps per preset
- ✅ **Number Entities**: Easy preset temperature configuration (8 entities)
- ✅ **Manual Override Tracking**: Binary sensor + clear button
- ✅ **Smart 8°C Mode**: Auto frost protection for Away/Sleep heat presets after configurable threshold
- ✅ **Cycle Management**: Optional compressor protection
- ✅ **HVAC Action**: Real-time heating/cooling/idle status
- ✅ **Smart Units**: Auto °F/°C detection and conversion
- ✅ **Full Persistence**: All settings survive restarts

## Documentation

Full documentation available in [`docs/README.md`](docs/README.md)

## Releases

See [GitHub Releases](https://github.com/rpulivella/GreeComfort/releases) for the changelog.

## Credits

- **Original Integration**: [RobHofmann/HomeAssistant-GreeClimateComponent](https://github.com/RobHofmann/HomeAssistant-GreeClimateComponent) v3.3.2
- **Domain**: `gree_comfort` (distinct from the HACS `gree` domain — both can coexist)
