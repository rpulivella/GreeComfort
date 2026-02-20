# Gree Comfort - Custom Home Assistant Integration

Enhanced Gree HVAC integration with comfort modes, manual override tracking, and cycle management.

## Project Structure

```
GreeCustom/
├── custom_components/
│   └── gree_comfort/          # Working integration (ready to install)
├── reference-original/
│   └── gree/                  # Original RobHofmann integration (for reference)
├── docs/
│   ├── README.md              # Full feature documentation
│   └── IMPLEMENTATION_PLAN.md # Technical implementation details
├── .gitignore                 # Git ignore rules
├── install.sh                 # Installation script
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
- ✅ **Number Entities**: Easy preset temperature configuration (7 entities)
- ✅ **Manual Override Tracking**: Binary sensor + clear button
- ✅ **Cycle Management**: Optional compressor protection
- ✅ **HVAC Action**: Real-time heating/cooling/idle status
- ✅ **Smart Units**: Auto °F/°C detection and conversion
- ✅ **Full Persistence**: All settings survive restarts

## Documentation

Full documentation available in [`docs/README.md`](docs/README.md)

## Version

- **Current**: 3.3.2-comfort (2026-02-01)
- **Base**: RobHofmann/HomeAssistant-GreeClimateComponent v3.3.2
- **Domain**: `gree_comfort` (separate from HACS version)

## Credits

- **Original Integration**: [RobHofmann](https://github.com/RobHofmann/HomeAssistant-GreeClimateComponent)
- **Comfort Mode Features**: Custom modifications
