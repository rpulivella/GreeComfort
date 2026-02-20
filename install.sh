#!/bin/bash
#
# Installation script for Gree Comfort Integration
#

set -e

echo "================================================"
echo "Gree Comfort Integration - Custom Install"
echo "================================================"
echo ""

# Check if HA config path is provided
if [ -z "$1" ]; then
    echo "Usage: ./install.sh /path/to/homeassistant/config"
    echo ""
    echo "Example:"
    echo "  ./install.sh /home/homeassistant/.homeassistant"
    echo "  ./install.sh /config"
    echo ""
    exit 1
fi

HA_CONFIG="$1"

# Verify HA config directory exists
if [ ! -d "$HA_CONFIG" ]; then
    echo "❌ Error: Home Assistant config directory not found: $HA_CONFIG"
    exit 1
fi

# Check if configuration.yaml exists (sanity check)
if [ ! -f "$HA_CONFIG/configuration.yaml" ]; then
    echo "⚠️  Warning: configuration.yaml not found in $HA_CONFIG"
    echo "   Are you sure this is your HA config directory?"
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

CUSTOM_COMPONENTS="$HA_CONFIG/custom_components"
DEST="$CUSTOM_COMPONENTS/gree_comfort"

# Create custom_components if it doesn't exist
if [ ! -d "$CUSTOM_COMPONENTS" ]; then
    echo "📁 Creating custom_components directory..."
    mkdir -p "$CUSTOM_COMPONENTS"
fi

# Check if gree_comfort already exists
if [ -d "$DEST" ]; then
    echo "⚠️  Warning: $DEST already exists"
    echo ""
    echo "This will be backed up to: ${DEST}.backup.$(date +%Y%m%d_%H%M%S)"
    read -p "Continue? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        echo "Installation cancelled."
        exit 1
    fi

    # Backup existing
    BACKUP="${DEST}.backup.$(date +%Y%m%d_%H%M%S)"
    echo "📦 Backing up existing installation to: $BACKUP"
    mv "$DEST" "$BACKUP"
fi

# Copy files
echo "📋 Copying Gree Comfort integration to $DEST..."
cp -r "custom_components/gree_comfort" "$DEST"

echo ""
echo "✅ Installation complete!"
echo ""
echo "Next steps:"
echo "1. If you had HACS Gree integration installed:"
echo "   HACS → Integrations → Gree Climate → Remove"
echo "   Settings → Devices & Services → Gree Climate → Delete"
echo ""
echo "2. Restart Home Assistant"
echo ""
echo "3. Add the integration:"
echo "   Settings → Devices & Services → Add Integration → Gree Comfort"
echo ""
echo "4. Configure preset temperatures via number entities:"
echo "   Settings → Devices & Services → Gree Comfort → [Device] → Number entities"
echo ""
echo "================================================"
