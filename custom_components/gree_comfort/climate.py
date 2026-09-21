"""
Gree Climate Entity for Home Assistant.

This module defines the climate (HVAC) unit for the Gree integration.
"""

# Standard library imports
import base64
import logging
from collections import deque
from datetime import timedelta, datetime

# Third-party imports
try:
    import simplejson
except ImportError:
    import json as simplejson
from Crypto.Cipher import AES

# Home Assistant imports
from homeassistant.components.climate import ClimateEntity, ClimateEntityFeature, HVACMode, HVACAction
from homeassistant.const import (
    ATTR_TEMPERATURE,
    ATTR_UNIT_OF_MEASUREMENT,
    CONF_HOST,
    CONF_MAC,
    CONF_NAME,
    CONF_PORT,
)
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.storage import Store
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers import issue_registry as ir
from homeassistant.const import UnitOfTemperature
from homeassistant.util import dt as dt_util
from homeassistant.util.unit_conversion import TemperatureConverter

# Local imports
from .const import (
    DOMAIN,
    DEFAULT_PORT,
    DEFAULT_HVAC_MODES,
    DEFAULT_FAN_MODES,
    DEFAULT_SWING_MODES,
    DEFAULT_SWING_HORIZONTAL_MODES,
    DEFAULT_TARGET_TEMP_STEP,
    MIN_TEMP_C,
    MIN_TEMP_F,
    MAX_TEMP_C,
    MAX_TEMP_F,
    MODES_MAPPING,
    TEMSEN_OFFSET,
    CONF_HVAC_MODES,
    CONF_FAN_MODES,
    CONF_SWING_MODES,
    CONF_SWING_HORIZONTAL_MODES,
    CONF_ENCRYPTION_KEY,
    CONF_UID,
    CONF_ENCRYPTION_VERSION,
    CONF_DISABLE_AVAILABLE_CHECK,
    CONF_TEMP_SENSOR_OFFSET,
)
from .gree_protocol import Pad, FetchResult, GetDeviceKey, GetGCMCipher, EncryptGCM, GetDeviceKeyGCM
from .helpers import TempOffsetResolver, gree_f_to_c, gree_c_to_f, encode_temp_c, decode_temp_c

REQUIREMENTS = ["pycryptodome"]

_LOGGER = logging.getLogger(__name__)

# Preset mode constants
PRESET_HOME = "home"
PRESET_SLEEP = "sleep"
PRESET_AWAY = "away"
PRESET_OFF = "off"
PRESET_NONE = "none"

PRESET_MODES = [PRESET_NONE, PRESET_HOME, PRESET_SLEEP, PRESET_AWAY, PRESET_OFF]

# Storage for persistence
STORAGE_KEY = "gree_climate_storage"
STORAGE_VERSION = 1

SUPPORT_FLAGS = (
    ClimateEntityFeature.TARGET_TEMPERATURE
    | ClimateEntityFeature.FAN_MODE
    | ClimateEntityFeature.PRESET_MODE
    | ClimateEntityFeature.TURN_ON
    | ClimateEntityFeature.TURN_OFF
)


async def create_gree_device(hass, config):
    """Create a Gree device instance from config."""
    name = config.get(CONF_NAME, "Gree Climate")
    ip_addr = config.get(CONF_HOST)
    port = config.get(CONF_PORT, DEFAULT_PORT)
    mac_addr = config.get(CONF_MAC).encode().replace(b":", b"")

    chm = config.get(CONF_HVAC_MODES)
    hvac_modes = [getattr(HVACMode, mode.upper()) for mode in (chm if chm is not None else DEFAULT_HVAC_MODES)]

    cfm = config.get(CONF_FAN_MODES)
    fan_modes = cfm if cfm is not None else DEFAULT_FAN_MODES
    csm = config.get(CONF_SWING_MODES)
    swing_modes = csm if csm is not None else DEFAULT_SWING_MODES
    cshm = config.get(CONF_SWING_HORIZONTAL_MODES)
    swing_horizontal_modes = cshm if cshm is not None else DEFAULT_SWING_HORIZONTAL_MODES
    encryption_key = config.get(CONF_ENCRYPTION_KEY)
    uid = config.get(CONF_UID)
    encryption_version = config.get(CONF_ENCRYPTION_VERSION, 1)
    disable_available_check = config.get(CONF_DISABLE_AVAILABLE_CHECK, False)
    temp_sensor_offset = config.get(CONF_TEMP_SENSOR_OFFSET)

    # Load preset temperature options
    use_fahrenheit = hass.config.units.temperature_unit == UnitOfTemperature.FAHRENHEIT

    preset_options = {
        "preset_home_heat": config.get("preset_home_heat"),
        "preset_home_cool": config.get("preset_home_cool"),
        "preset_sleep_heat": config.get("preset_sleep_heat"),
        "preset_sleep_cool": config.get("preset_sleep_cool"),
        "preset_away_heat": config.get("preset_away_heat"),
        "preset_away_cool": config.get("preset_away_cool"),
        "use_fahrenheit": use_fahrenheit,
    }

    return GreeClimate(
        hass,
        name,
        ip_addr,
        port,
        mac_addr,
        hvac_modes,
        fan_modes,
        swing_modes,
        swing_horizontal_modes,
        encryption_version,
        disable_available_check,
        encryption_key,
        uid,
        temp_sensor_offset,
        preset_options,
    )


# from the remote control and gree app

# update() interval - poll at 10s for accurate idle detection without hammering the device
SCAN_INTERVAL = timedelta(seconds=10)

# Eco Shutoff: seconds the auxiliary sensor may be unavailable while unit is off before
# power is restored as a safety measure.
ECO_SHUTOFF_SENSOR_TIMEOUT_S = 600
# Eco Shutoff: max age of sensor's last_reported timestamp before treating it as stale.
# 2× the Zigbee max reporting interval (3600s) — absorbs coordinator jitter that can delay
# reports by 60–100 min, preventing false-positive stale restores.
ECO_SHUTOFF_SENSOR_STALE_S = 120 * 60  # 7200s


async def async_setup_entry(hass, entry, async_add_devices):
    """Set up Gree climate from a config entry."""
    # Get the device that was created in __init__.py
    entry_data = hass.data[DOMAIN][entry.entry_id]
    device = entry_data["device"]

    async_add_devices([device])


async def async_unload_entry(hass, entry):
    """Unload a config entry."""
    return True


class GreeClimate(ClimateEntity):
    # Language is retrieved from translation key
    _attr_translation_key = "gree"

    def __init__(
        self,
        hass,
        name,
        ip_addr,
        port,
        mac_addr,
        hvac_modes,
        fan_modes,
        swing_modes,
        swing_horizontal_modes,
        encryption_version,
        disable_available_check,
        encryption_key=None,
        uid=None,
        temp_sensor_offset=None,
        preset_options=None,
    ):
        _LOGGER.info(f"{name}: Initializing Gree climate device")

        self.hass = hass
        self._name = name
        self._ip_addr = ip_addr
        self._port = port
        mac_addr_str = mac_addr.decode("utf-8").lower()
        if "@" in mac_addr_str:
            self._sub_mac_addr, self._mac_addr = mac_addr_str.split("@", 1)
        else:
            self._sub_mac_addr = self._mac_addr = mac_addr_str
        self._unique_id = f"{DOMAIN}_{self._sub_mac_addr}"
        self._device_online = None
        self._disable_available_check = disable_available_check

        self._target_temperature = None
        # Initialize target temperature step with default value (will be overridden by number entity when available)
        self._target_temperature_step = DEFAULT_TARGET_TEMP_STEP
        # Device uses a combination of Celsius + a set bit for Fahrenheit, so the integration needs to be aware of the units.
        self._unit_of_measurement = hass.config.units.temperature_unit
        _LOGGER.info(f"{self._name}: Unit of measurement: {self._unit_of_measurement}")

        self._hvac_modes = hvac_modes
        self._hvac_mode = HVACMode.OFF
        self._fan_modes = fan_modes
        self._fan_mode = None
        self._swing_modes = swing_modes
        self._swing_mode = None
        self._swing_horizontal_modes = swing_horizontal_modes
        self._swing_horizontal_mode = None

        self._temp_sensor_offset = temp_sensor_offset

        # Eco Shutoff auxiliary sensor (set by select entity; used only by SPO logic)
        self._eco_shutoff_sensor = None

        # Keep unsub callbacks for deregistering listeners
        self._listeners: list = []

        self._has_temp_sensor = None
        self._has_anti_direct_blow = None
        self._has_light_sensor = None
        self._has_outside_temp_sensor = None
        self._has_room_humidity_sensor = None

        self._current_temperature = None
        self._current_anti_direct_blow = None
        self._current_light_sensor = None
        self._current_outside_temperature = None
        self._current_room_humidity = None

        self._firstTimeRun = True

        self._enable_turn_on_off_backwards_compatibility = False

        self.encryption_version = encryption_version
        self.CIPHER = None

        if encryption_key:
            _LOGGER.info(f"{self._name}: Using configured encryption key: {encryption_key}")
            self._encryption_key = encryption_key.encode("utf8")
            if encryption_version == 1:
                # Cipher to use to encrypt/decrypt
                self.CIPHER = AES.new(self._encryption_key, AES.MODE_ECB)
            elif self.encryption_version != 2:
                _LOGGER.error(f"{self._name}: Encryption version {self.encryption_version} is not implemented")
        else:
            self._encryption_key = None

        if uid:
            self._uid = uid
        else:
            self._uid = 0

        self._acOptions = {
            "Pow": None,
            "Mod": None,
            "SetTem": None,
            "WdSpd": None,
            "Air": None,
            "Blo": None,
            "Health": None,
            "SwhSlp": None,
            "Lig": None,
            "SwingLfRig": None,
            "SwUpDn": None,
            "Quiet": None,
            "Tur": None,
            "StHt": None,
            "TemUn": None,
            "HeatCoolType": None,
            "TemRec": None,
            "SvSt": None,
            "SlpMod": None,
        }
        self._optionsToFetch = ["Pow", "Mod", "SetTem", "WdSpd", "Air", "Blo", "Health", "SwhSlp", "Lig", "SwingLfRig", "SwUpDn", "Quiet", "Tur", "StHt", "TemUn", "HeatCoolType", "TemRec", "SvSt", "SlpMod"]

        # Initialize auto switches
        self._auto_light = False
        self._auto_xfan = False

        # Initialize beeper control
        self._beeper_enabled = True  # Default to beeper ON (silent mode OFF)

        # Initialize preset mode state
        self._preset_mode = PRESET_NONE
        self._manual_override = False
        self._last_non_auto_hvac_mode = HVACMode.HEAT  # Track last Heat/Cool mode for Auto fallback

        # Track last hvac_action for direction-change detection (slope = 0 case)
        self._last_hvac_action = HVACAction.IDLE

        # Load preset temperatures from options or use defaults
        if preset_options:
            use_fahrenheit = preset_options.get("use_fahrenheit", False)

            def load_temp(key, default_c, default_f):
                """Load temp from options and convert to Celsius if needed."""
                default = default_f if use_fahrenheit else default_c
                temp = preset_options.get(key, default)
                if temp is None:
                    temp = default
                # Simple F to C conversion (gree_f_to_c returns a tuple for device protocol)
                return (temp - 32.0) * 5.0 / 9.0 if use_fahrenheit else temp

            self._preset_temps = {
                PRESET_HOME: {
                    "heat": load_temp("preset_home_heat", 20, 68),
                    "cool": load_temp("preset_home_cool", 24, 75),
                },
                PRESET_SLEEP: {
                    "heat": load_temp("preset_sleep_heat", 17, 62),
                    "cool": load_temp("preset_sleep_cool", 26, 78),
                },
                PRESET_AWAY: {
                    "heat": load_temp("preset_away_heat", 15, 59),
                    "cool": load_temp("preset_away_cool", 28, 82),
                },
            }

        else:
            # Default preset temperatures in Celsius
            self._preset_temps = {
                PRESET_HOME: {"heat": 20, "cool": 24},
                PRESET_SLEEP: {"heat": 17, "cool": 26},
                PRESET_AWAY: {"heat": 15, "cool": 28},
            }

        # Smart 8°C mode state (defaults; updated by switch/number entity restore)
        self._stht_smart_enabled = True
        self._stht_smart_threshold_minutes = 60
        self._stht_smart_active = False
        self._preset_active_since = None
        self._scheduled_preset = None  # What the time-based schedule says right now

        # Schedule auto-release: when enabled, a scheduled preset change clears any active
        # manual override and applies the preset immediately (as if the button were pressed).
        # Default is False — override is always respected unless the user explicitly clears it.
        #
        # TODO(future): Consider replacing this toggle with a counter (0–6) where the value
        # represents how many scheduled preset changes are allowed to be skipped before the
        # override is automatically cleared. 0 = never auto-clear (current default behavior),
        # 1 = same as this toggle "on", 2–6 = allow N skips before yielding to the schedule.
        # This would give forgetful-household tolerance without fully surrendering manual control.
        self._schedule_auto_release = False

        # Temperature history for HVAC action idle detection (150 seconds at 10s polling)
        self._temp_history = deque(maxlen=15)

        # Eco Shutoff state
        self._eco_shutoff_enabled = False
        self._eco_shutoff_active = False
        self._eco_shutoff_sensor_missing_s = 0
        self._eco_shutoff_satisfied_since: datetime | None = None
        # Tunable parameters (defaults; overridden by number entity restore)
        self._eco_shutoff_satisfied_margin = 1.5   # °C past setpoint before shutoff
        self._eco_shutoff_reengage_delta = 0.5     # °C from setpoint before power-on
        self._eco_shutoff_trend_window_minutes = 5  # minutes room must stay satisfied

        # Storage for preset persistence
        self._storage = Store(hass, STORAGE_VERSION, f"{STORAGE_KEY}_{name}")

        # helper method to determine TemSen offset
        self._process_temp_sensor = TempOffsetResolver()

    async def GreeGetValues(self, propertyNames):
        plaintext = '{"cols":' + simplejson.dumps(propertyNames) + ',"mac":"' + str(self._sub_mac_addr) + '","t":"status"}'
        if self.encryption_version == 1:
            cipher = self.CIPHER
            jsonPayloadToSend = '{"cid":"app","i":0,"pack":"' + base64.b64encode(cipher.encrypt(Pad(plaintext).encode("utf8"))).decode("utf-8") + '","t":"pack","tcid":"' + str(self._mac_addr) + '","uid":{}'.format(self._uid) + "}"
        elif self.encryption_version == 2:
            pack, tag = EncryptGCM(self._encryption_key, plaintext)
            jsonPayloadToSend = '{"cid":"app","i":0,"pack":"' + pack + '","t":"pack","tcid":"' + str(self._mac_addr) + '","uid":{}'.format(self._uid) + ',"tag" : "' + tag + '"}'
            cipher = GetGCMCipher(self._encryption_key)
        result = await FetchResult(cipher, self._ip_addr, self._port, jsonPayloadToSend, encryption_version=self.encryption_version)
        return result["dat"][0] if len(result["dat"]) == 1 else result["dat"]

    def SetAcOptions(self, acOptions, newOptionsToOverride, optionValuesToOverride=None):
        if optionValuesToOverride is not None:
            # Build a list of key-value pairs for a single log line
            settings = []
            for key in newOptionsToOverride:
                value = optionValuesToOverride[newOptionsToOverride.index(key)]
                settings.append(f"{key}={value}")
                acOptions[key] = value
            _LOGGER.debug(f"{self._name}: Setting device options with retrieved values: {', '.join(settings)}")
        else:
            # Build a list of key-value pairs for a single log line
            settings = []
            for key, value in newOptionsToOverride.items():
                settings.append(f"{key}={value}")
                acOptions[key] = value
            _LOGGER.debug(f"{self._name}: Overwriting device options with new settings: {', '.join(settings)}")
        return acOptions

    async def SendStateToAc(self):
        opt_list = ["Pow", "Mod", "SetTem", "WdSpd", "Air", "Blo", "Health", "SwhSlp", "Lig", "SwingLfRig", "SwUpDn", "Quiet", "Tur", "StHt", "TemUn", "HeatCoolType", "TemRec", "SvSt", "SlpMod", "AntiDirectBlow", "LigSen"]

        # Collect values from _acOptions
        p_values = [self._acOptions.get(k) for k in opt_list]

        # Filter out empty ones
        filtered_opt = []
        filtered_p = []
        for name, val in zip(opt_list, p_values):
            if val not in ("", None):
                filtered_opt.append(f'"{name}"')
                filtered_p.append(str(val))

        buzzer_command_value = 0 if self._beeper_enabled else 1
        filtered_opt.append('"Buzzer_ON_OFF"')
        filtered_p.append(str(buzzer_command_value))
        _LOGGER.debug(f"{self._name}: Sending command with beeper {'enabled' if self._beeper_enabled else 'disabled'} (buzzer={buzzer_command_value})")

        statePackJson = '{"opt":[' + ",".join(filtered_opt) + '],"p":[' + ",".join(filtered_p) + '],"t":"cmd","sub":"' + self._sub_mac_addr + '"}'

        if self.encryption_version == 1:
            cipher = self.CIPHER
            sentJsonPayload = '{"cid":"app","i":0,"pack":"' + base64.b64encode(cipher.encrypt(Pad(statePackJson).encode("utf8"))).decode("utf-8") + '","t":"pack","tcid":"' + str(self._mac_addr) + '","uid":{}'.format(self._uid) + "}"
        elif self.encryption_version == 2:
            pack, tag = EncryptGCM(self._encryption_key, statePackJson)
            sentJsonPayload = '{"cid":"app","i":0,"pack":"' + pack + '","t":"pack","tcid":"' + str(self._mac_addr) + '","uid":{}'.format(self._uid) + ',"tag":"' + tag + '"}'
            cipher = GetGCMCipher(self._encryption_key)
        result = await FetchResult(cipher, self._ip_addr, self._port, sentJsonPayload, encryption_version=self.encryption_version)
        _LOGGER.debug(f"{self._name}: Command sent successfully: {str(result)}")

    def UpdateHATargetTemperature(self):
        # Sync set temperature to HA. If 8℃ heating is active we set the temp in HA to 8℃ so that it shows the same as the AC display.
        if self._acOptions["StHt"] and (int(self._acOptions["StHt"]) == 1):
            if self._unit_of_measurement == UnitOfTemperature.FAHRENHEIT:
                self._target_temperature = (8.0 * 9.0 / 5.0) + 32.0  # 8°C → °F
            else:
                self._target_temperature = 8
            _LOGGER.debug(f"{self._name}: Target temperature set to {self._target_temperature}{self._unit_of_measurement} for 8°C heating mode")
        else:
            temp_c = decode_temp_c(SetTem=self._acOptions["SetTem"], TemRec=self._acOptions["TemRec"])  # takes care of 1/2 degrees
            temp_f = gree_c_to_f(SetTem=self._acOptions["SetTem"], TemRec=self._acOptions["TemRec"])

            if self._unit_of_measurement == "°C":
                display_temp = temp_c
            elif self._unit_of_measurement == "°F":
                display_temp = temp_f
            else:
                display_temp = temp_c  # default to deg c
                _LOGGER.error(f"{self._name}: Unknown unit of measurement: {self._unit_of_measurement}")

            self._target_temperature = display_temp

            _LOGGER.debug(f"{self._name}: Target temperature set to {self._target_temperature}{self._unit_of_measurement}")

    def UpdateHAHvacMode(self):
        # Sync current HVAC operation mode to HA
        if self._acOptions["Pow"] == 0:
            if not self._eco_shutoff_active:
                self._hvac_mode = HVACMode.OFF
            # else: eco shutoff owns this power-off — preserve mode so re-engage logic and
            # hvac_action can run correctly; the unit is idle, not user-off
        else:
            for key, value in MODES_MAPPING.get("Mod").items():
                if value == (self._acOptions["Mod"]):
                    self._hvac_mode = key

        # Track last non-Auto mode for smart fallback when clearing override from Auto
        if self._hvac_mode in (HVACMode.HEAT, HVACMode.COOL):
            self._last_non_auto_hvac_mode = self._hvac_mode
            _LOGGER.debug(f"{self._name}: Tracked last non-auto mode: {self._last_non_auto_hvac_mode}")

        _LOGGER.debug(f"{self._name}: HVAC mode updated to {self._hvac_mode}")

    def UpdateHACurrentSwingMode(self):
        # Sync current HVAC Swing mode state to HA
        for key, value in MODES_MAPPING.get("SwUpDn").items():
            if value == (self._acOptions["SwUpDn"]):
                self._swing_mode = key
        _LOGGER.debug(f"{self._name}: Swing mode updated to {self._swing_mode}")

    def UpdateHACurrentSwingHorizontalMode(self):
        # Sync current HVAC Horizontal Swing mode state to HA
        for key, value in MODES_MAPPING.get("SwingLfRig").items():
            if value == (self._acOptions["SwingLfRig"]):
                self._swing_horizontal_mode = key
        _LOGGER.debug(f"{self._name}: Horizontal swing mode updated to {self._swing_horizontal_mode}")

    def UpdateHAFanMode(self):
        # Sync current HVAC Fan mode state to HA
        if int(self._acOptions["Tur"]) == 1:
            turbo_index = self._fan_modes.index("turbo")
            self._fan_mode = self._fan_modes[turbo_index]
        elif int(self._acOptions["Quiet"]) >= 1:
            quiet_index = self._fan_modes.index("quiet")
            self._fan_mode = self._fan_modes[quiet_index]
        else:
            for key, value in MODES_MAPPING.get("WdSpd").items():
                if value == (self._acOptions["WdSpd"]):
                    self._fan_mode = key
        _LOGGER.debug(f"{self._name}: Fan mode updated to {self._fan_mode}")

    def UpdateHACurrentTemperature(self):
        # Use built-in AC temperature sensor if available
        if self._has_temp_sensor:
            _LOGGER.debug(f"{self._name}: Built-in temperature sensor reading: {self._acOptions['TemSen']}")

            if self._temp_sensor_offset is None:  # user hasn't chosen an offset
                # User hasn't set automaticaly, so try to determine the offset
                temp_c = self._process_temp_sensor(self._acOptions["TemSen"])
                _LOGGER.debug("method UpdateHACurrentTemperature: User has not chosen an offset, using process_temp_sensor() to automatically determine offset.")
            else:
                # User set
                if self._temp_sensor_offset is True:
                    temp_c = self._acOptions["TemSen"] - TEMSEN_OFFSET

                elif self._temp_sensor_offset is False:
                    temp_c = self._acOptions["TemSen"]

                _LOGGER.debug(f"method UpdateHACurrentTemperature: User has chosen an offset ({self._temp_sensor_offset})")

            temp_f = gree_c_to_f(SetTem=temp_c, TemRec=0)  # Convert to Fahrenheit using TemRec bit

            if self._unit_of_measurement == "°C":
                self._current_temperature = temp_c
            elif self._unit_of_measurement == "°F":
                self._current_temperature = temp_f
            else:
                _LOGGER.error("Unknown unit of measurement: %s" % self._unit_of_measurement)

            _LOGGER.debug(f"{self._name}: UpdateHACurrentTemperature: HA current temperature set with device built-in temperature sensor state: {self._current_temperature}{self._unit_of_measurement}")

    def UpdateHAOutsideTemperature(self):
        # Update outside temperature from built-in AC outside temperature sensor if available
        if self._has_outside_temp_sensor:
            _LOGGER.debug(f"{self._name}: UpdateHAOutsideTemperature: OutEnvTem: {self._acOptions['OutEnvTem']}")

            if self._temp_sensor_offset is None:  # user hasn't chosen an offset
                # User hasn't set automatically, so try to determine the offset
                temp_c = self._process_temp_sensor(self._acOptions["OutEnvTem"])
                _LOGGER.debug("method UpdateHAOutsideTemperature: User has not chosen an offset, using process_temp_sensor() to automatically determine offset.")
            else:
                # User set
                if self._temp_sensor_offset is True:
                    temp_c = self._acOptions["OutEnvTem"] - TEMSEN_OFFSET
                elif self._temp_sensor_offset is False:
                    temp_c = self._acOptions["OutEnvTem"]

                _LOGGER.debug(f"method UpdateHAOutsideTemperature: User has chosen an offset ({self._temp_sensor_offset})")

            temp_f = gree_c_to_f(SetTem=temp_c, TemRec=0)  # Convert to Fahrenheit using TemRec bit

            if self._unit_of_measurement == "°C":
                self._current_outside_temperature = temp_c
            elif self._unit_of_measurement == "°F":
                self._current_outside_temperature = temp_f
            else:
                _LOGGER.error("Unknown unit of measurement for outside temperature: %s" % self._unit_of_measurement)

            _LOGGER.debug(f"{self._name}: UpdateHAOutsideTemperature: HA outside temperature set with device built-in outside temperature sensor state: {self._current_outside_temperature}{self._unit_of_measurement}")

    def UpdateHARoomHumidity(self):
        # Update room humidity from built-in AC room humidity sensor if available
        if self._has_room_humidity_sensor:
            _LOGGER.debug(f"{self._name}: UpdateHARoomHumidity: DwatSen: {self._acOptions['DwatSen']}")
            self._current_room_humidity = self._acOptions["DwatSen"]
            _LOGGER.debug(f"{self._name}: UpdateHARoomHumidity: HA room humidity set with device built-in room humidity sensor state: {self._current_room_humidity}%")

    def _update_temp_history(self):
        """Update temperature history for idle detection."""
        if self._current_temperature is not None:
            self._temp_history.append(self._current_temperature)
            _LOGGER.debug(f"{self._name}: Temp history: {list(self._temp_history)}")

    def UpdateHAStateToCurrentACState(self):
        self.UpdateHATargetTemperature()
        self.UpdateHAHvacMode()
        self.UpdateHACurrentSwingMode()
        self.UpdateHACurrentSwingHorizontalMode()
        self.UpdateHAFanMode()
        self.UpdateHACurrentTemperature()
        self.UpdateHAOutsideTemperature()
        self.UpdateHARoomHumidity()

        # Update temperature history for trend tracking
        self._update_temp_history()

        # Check if device temperature or mode differs from expected preset
        # (detects manual changes made on physical device)
        self._recalculate_manual_override()

    async def SyncState(self, acOptions={}):
        # Fetch current settings from HVAC
        _LOGGER.debug(f"{self._name}: Starting device state sync")

        if self._has_temp_sensor is None:
            _LOGGER.debug("Attempt to check whether device has an built-in temperature sensor")
            try:
                temp_sensor = await self.GreeGetValues(["TemSen"])
            except Exception:
                _LOGGER.debug("Could not determine whether device has an built-in temperature sensor. Retrying at next update()")
            else:
                if temp_sensor:
                    self._has_temp_sensor = True
                    self._acOptions.update({"TemSen": None})
                    self._optionsToFetch.append("TemSen")
                    _LOGGER.debug("Device has an built-in temperature sensor")
                else:
                    self._has_temp_sensor = False
                    _LOGGER.debug("Device has no built-in temperature sensor")

        # Check if device has anti direct blow feature
        if self._has_anti_direct_blow is None:
            _LOGGER.debug("Attempt to check whether device has an anti direct blow feature")
            try:
                anti_direct_blow = await self.GreeGetValues(["AntiDirectBlow"])
            except Exception:
                _LOGGER.debug("Could not determine whether device has an anti direct blow feature. Retrying at next update()")
            else:
                if anti_direct_blow:
                    self._has_anti_direct_blow = True
                    self._acOptions.update({"AntiDirectBlow": None})
                    self._optionsToFetch.append("AntiDirectBlow")
                    _LOGGER.debug("Device has an anti direct blow feature")
                else:
                    self._has_anti_direct_blow = False
                    _LOGGER.debug("Device has no anti direct blow feature")

        # Check if device has light sensor
        if self._has_light_sensor is None:
            _LOGGER.debug("Attempt to check whether device has a built-in light sensor")
            try:
                light_sensor = await self.GreeGetValues(["LigSen"])
            except Exception:
                _LOGGER.debug("Could not determine whether device has a built-in light sensor. Retrying at next update()")
            else:
                if light_sensor:
                    self._has_light_sensor = True
                    self._acOptions.update({"LigSen": None})
                    self._optionsToFetch.append("LigSen")
                    _LOGGER.debug("Device has a built-in light sensor")
                else:
                    self._has_light_sensor = False
                    _LOGGER.debug("Device has no built-in light sensor")

        # Check if device has outside temperature sensor
        if self._has_outside_temp_sensor is None:
            _LOGGER.debug("Attempt to check whether device has an outside temperature sensor")
            try:
                outside_temp_sensor = await self.GreeGetValues(["OutEnvTem"])
            except Exception:
                _LOGGER.debug("Could not determine whether device has an outside temperature sensor. Retrying at next update()")
            else:
                if outside_temp_sensor:
                    self._has_outside_temp_sensor = True
                    self._acOptions.update({"OutEnvTem": None})
                    self._optionsToFetch.append("OutEnvTem")
                    _LOGGER.debug("Device has an outside temperature sensor")
                else:
                    self._has_outside_temp_sensor = False
                    _LOGGER.debug("Device has no outside temperature sensor")

        # Check if device has room humidity sensor
        if self._has_room_humidity_sensor is None:
            _LOGGER.debug("Attempt to check whether device has a room humidity sensor")
            try:
                humidity_sensor = await self.GreeGetValues(["DwatSen"])
            except Exception:
                _LOGGER.debug("Could not determine whether device has a room humidity sensor. Retrying at next update()")
            else:
                if humidity_sensor:
                    self._has_room_humidity_sensor = True
                    self._acOptions.update({"DwatSen": None})
                    self._optionsToFetch.append("DwatSen")
                    _LOGGER.debug("Device has a room humidity sensor")
                else:
                    self._has_room_humidity_sensor = False
                    _LOGGER.debug("Device has no room humidity sensor")

        optionsToFetch = self._optionsToFetch

        try:
            currentValues = await self.GreeGetValues(optionsToFetch)
        except Exception as e:
            _LOGGER.warning(f"{self._name}: Failed to communicate with device {self._ip_addr}:{self._port}: {str(e)}")
            if not self._disable_available_check:
                _LOGGER.info(f"{self._name}: Device marked offline after failed communication")
                self._device_online = False
        else:
            if not self._disable_available_check:
                if not self._device_online:
                    self._device_online = True
            # Set latest status from device
            self._acOptions = self.SetAcOptions(self._acOptions, optionsToFetch, currentValues)

            # Overwrite status with our choices
            if not (acOptions == {}):
                self._acOptions = self.SetAcOptions(self._acOptions, acOptions)

            # If not the first (boot) run, update state towards the HVAC
            if not (self._firstTimeRun):
                if not (acOptions == {}):
                    # loop used to send changed settings from HA to HVAC
                    try:
                        await self.SendStateToAc()
                    except Exception as e:
                        _LOGGER.warning(f"{self._name}: Failed to send state to device {self._ip_addr}:{self._port}: {str(e)}")
                        # Mark device as offline if communication fails
                        if not self._disable_available_check:
                            _LOGGER.info(f"{self._name}: Device marked offline after failed send attempt")
                            self._device_online = False
            else:
                # loop used once for Gree Climate initialisation only
                self._firstTimeRun = False

            # Update HA state to current HVAC state
            self.UpdateHAStateToCurrentACState()

            _LOGGER.debug(f"{self._name}: Finished device state sync")

    @property
    def should_poll(self):
        _LOGGER.debug("should_poll()")
        # Return the polling state.
        return True

    @property
    def available(self):
        if self._disable_available_check:
            return True
        else:
            if self._device_online:
                _LOGGER.debug("available(): Device is online")
                return True
            else:
                _LOGGER.debug("available(): Device is offline")
                return False

    async def async_update(self):
        """Retrieve latest state."""
        _LOGGER.debug("async_update()")
        if not self._encryption_key:
            if self.encryption_version == 1:
                key = await GetDeviceKey(self._mac_addr, self._ip_addr, self._port)
                if key:
                    self._encryption_key = key
                    self.CIPHER = AES.new(self._encryption_key, AES.MODE_ECB)
                    await self.SyncState()
            elif self.encryption_version == 2:
                key = await GetDeviceKeyGCM(self._mac_addr, self._ip_addr, self._port)
                if key:
                    self._encryption_key = key
                    self.CIPHER = GetGCMCipher(self._encryption_key)
                    await self.SyncState()
            else:
                _LOGGER.error("Encryption version %s is not implemented." % self.encryption_version)
        else:
            await self.SyncState()

        # Manage smart 8°C mode
        await self._manage_stht_auto()

        # Manage Eco Shutoff
        await self._check_eco_shutoff()

    @property
    def name(self):
        _LOGGER.debug(f"{self._name}: name() = {self._name}")
        # Return the name of the climate device.
        return self._name

    @property
    def temperature_unit(self):
        _LOGGER.debug(f"{self._name}: temperature_unit() = {self._unit_of_measurement}")
        # Return the unit of measurement.
        return self._unit_of_measurement

    @property
    def current_temperature(self):
        _LOGGER.debug(f"{self._name}: current_temperature() = {self._current_temperature}")
        # Return the current temperature.
        return self._current_temperature

    @property
    def min_temp(self):
        if self._unit_of_measurement == "°C":
            MIN_TEMP = MIN_TEMP_C
        else:
            MIN_TEMP = MIN_TEMP_F

        _LOGGER.debug(f"{self._name}: min_temp() = {MIN_TEMP}")
        # Return the minimum temperature.
        return MIN_TEMP

    @property
    def max_temp(self):
        if self._unit_of_measurement == "°C":
            MAX_TEMP = MAX_TEMP_C
        else:
            MAX_TEMP = MAX_TEMP_F

        _LOGGER.debug(f"{self._name}: max_temp() = {MAX_TEMP}")
        # Return the maximum temperature.
        return MAX_TEMP

    @property
    def target_temperature(self):
        _LOGGER.debug(f"{self._name}: target_temperature() = {self._target_temperature}")
        # Return the temperature we try to reach.
        return self._target_temperature

    @property
    def target_temperature_step(self):
        _LOGGER.debug(f"{self._name}: target_temperature_step() = {self._target_temperature_step}")
        return self._target_temperature_step

    @property
    def hvac_mode(self):
        _LOGGER.debug(f"{self._name}: hvac_mode() = {self._hvac_mode}")
        # Return current operation mode ie. heat, cool, idle.
        return self._hvac_mode

    def _linear_regression_slope(self, temps):
        """Calculate slope using linear regression on temperature sequence."""
        n = len(temps)
        if n < 2:
            return 0

        x_mean = (n - 1) / 2.0
        y_mean = sum(temps) / n

        numerator = sum((i - x_mean) * (temps[i] - y_mean) for i in range(n))
        denominator = sum((i - x_mean) ** 2 for i in range(n))

        if denominator == 0:
            return 0

        return numerator / denominator

    @property
    def hvac_action(self):
        """Return current HVAC action - what the unit is actually doing."""
        if self._eco_shutoff_active:
            return HVACAction.IDLE
        if not self._acOptions or self._acOptions.get('Pow') == 0:
            return HVACAction.OFF

        current_temp = self._current_temperature
        target_temp = self._target_temperature
        mode = self.hvac_mode

        # Handle modes that don't track temperature
        if mode == HVACMode.DRY:
            return HVACAction.DRYING
        elif mode == HVACMode.FAN_ONLY:
            return HVACAction.FAN

        # For heat/cool modes, determine if actively heating/cooling or idle
        if current_temp is None or target_temp is None:
            return HVACAction.IDLE

        # Direction-change idle detection using temperature trend
        # State changes ONLY on direction reversal (slope sign change)
        # When slope = 0, maintain previous state
        if len(self._temp_history) < 4:
            self._last_hvac_action = HVACAction.IDLE
            return HVACAction.IDLE  # Not enough data yet

        # Use last 10 readings for slope calculation (100 second window at 10s polling)
        history = list(self._temp_history)[-10:]
        slope = self._linear_regression_slope(history)

        _LOGGER.debug(f"{self._name}: Temp: {current_temp}, Slope: {slope:.3f}, Last action: {self._last_hvac_action}")

        # Auto mode: Cannot determine action without compressor feedback from device
        if mode == HVACMode.AUTO:
            return None  # Unknown - HA will show as unavailable

        # Heat mode: Temp rising = heating, temp falling = idle, temp flat = maintain state
        if mode == HVACMode.HEAT:
            if slope > 0:
                action = HVACAction.HEATING
            elif slope < 0:
                action = HVACAction.IDLE
            else:
                # Slope = 0: maintain previous action (direction hasn't changed)
                action = self._last_hvac_action

        # Cool mode: Temp falling = cooling, temp rising = idle, temp flat = maintain state
        elif mode == HVACMode.COOL:
            if slope < 0:
                action = HVACAction.COOLING
            elif slope > 0:
                action = HVACAction.IDLE
            else:
                # Slope = 0: maintain previous action (direction hasn't changed)
                action = self._last_hvac_action

        # Other modes (shouldn't reach here)
        else:
            action = HVACAction.IDLE

        # Store action for next slope=0 case
        self._last_hvac_action = action
        return action

    @property
    def swing_mode(self):
        if self._swing_modes:
            _LOGGER.debug(f"{self._name}: swing_mode() = {self._swing_mode}")
            # get the current swing mode
            return self._swing_mode
        else:
            return None

    @property
    def swing_modes(self):
        _LOGGER.debug(f"{self._name}: swing_modes() = {self._swing_modes}")
        # get the list of available swing modes
        return self._swing_modes

    @property
    def swing_horizontal_mode(self):
        if self._swing_horizontal_modes:
            _LOGGER.debug(f"{self._name}: swing_horizontal_mode() = {self._swing_horizontal_mode}")
            # get the current preset mode
            return self._swing_horizontal_mode
        else:
            return None

    @property
    def swing_horizontal_modes(self):
        _LOGGER.debug(f"{self._name}: swing_horizontal_modes() = {self._swing_horizontal_modes}")
        # get the list of available preset modes
        return self._swing_horizontal_modes

    @property
    def hvac_modes(self):
        _LOGGER.debug(f"{self._name}: hvac_modes() = {self._hvac_modes}")
        # get the list of available operation modes.
        return self._hvac_modes

    @property
    def preset_mode(self):
        _LOGGER.debug(f"{self._name}: preset_mode() = {self._preset_mode}")
        return self._preset_mode

    @property
    def preset_modes(self):
        _LOGGER.debug(f"{self._name}: preset_modes() = {PRESET_MODES}")
        return PRESET_MODES

    @property
    def fan_mode(self):
        _LOGGER.debug(f"{self._name}: fan_mode() = {self._fan_mode}")
        # Return the fan mode.
        return self._fan_mode

    @property
    def fan_modes(self):
        _LOGGER.debug(f"{self._name}: fan_modes() = {self._fan_modes}")
        # Return the list of available fan modes.
        return self._fan_modes

    @property
    def supported_features(self):
        sf = SUPPORT_FLAGS
        if self._swing_modes:
            sf = sf | ClimateEntityFeature.SWING_MODE
        if self._swing_horizontal_modes:
            sf = sf | ClimateEntityFeature.SWING_HORIZONTAL_MODE
        _LOGGER.debug(f"{self._name}: supported_features() = {sf}")
        # Return the list of supported features.
        return sf

    @property
    def unique_id(self):
        # Return unique_id
        return self._unique_id

    @property
    def device_info(self) -> DeviceInfo:
        """Return device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, self._mac_addr)},
            name=self._name,
            manufacturer="Gree",
            model="Mini-Split Heat Pump",
            suggested_area="Climate Control",
        )

    @property
    def outside_temperature(self):
        """Return the outside temperature if available."""
        if self._has_outside_temp_sensor:
            _LOGGER.debug(f"{self._name}: outside_temperature() = {self._current_outside_temperature}")
            return self._current_outside_temperature
        return None

    @property
    def room_humidity(self):
        """Return the current room humidity if available."""
        if self._has_room_humidity_sensor:
            _LOGGER.debug(f"{self._name}: room_humidity() = {self._current_room_humidity}")
            return self._current_room_humidity
        return None

    @property
    def extra_state_attributes(self):
        """Return additional state attributes."""
        attributes = {}

        # Add hvac_action
        attributes["hvac_action"] = self.hvac_action

        # Scheduled preset (what the time-based automation currently says)
        if self._scheduled_preset is not None:
            attributes["scheduled_preset"] = self._scheduled_preset

        # Add preset temperatures (rounded to 1 decimal place)
        rounded_temps = {}
        for preset, temps in self._preset_temps.items():
            rounded_temps[preset] = {
                "heat": round(temps["heat"], 1),
                "cool": round(temps["cool"], 1)
            }
        attributes["preset_temperatures_celsius"] = rounded_temps

        # Add manual override state
        attributes["manual_override"] = self._manual_override

        # Eco Shutoff state
        attributes["eco_shutoff_active"] = self._eco_shutoff_active
        if self._eco_shutoff_sensor:
            attributes["eco_shutoff_sensor"] = self._eco_shutoff_sensor

        # Smart 8°C mode debug info
        if self._stht_smart_enabled:
            elapsed_s = None
            if self._preset_active_since:
                elapsed_s = (datetime.now() - self._preset_active_since).total_seconds()
            threshold_s = self._stht_smart_threshold_minutes * 60
            if self._stht_smart_active:
                remaining_min = 0
            elif elapsed_s is not None:
                remaining_min = round(max(0.0, (threshold_s - elapsed_s) / 60), 1)
            else:
                remaining_min = self._stht_smart_threshold_minutes
            attributes["stht_smart"] = {
                "active": self._stht_smart_active,
                "preset_active_since": self._preset_active_since.isoformat() if self._preset_active_since else None,
                "elapsed_minutes": round(elapsed_s / 60, 1) if elapsed_s is not None else None,
                "remaining_minutes": remaining_min,
                "threshold_minutes": self._stht_smart_threshold_minutes,
            }

        if self.outside_temperature is not None:
            attributes["outside_temperature"] = self.outside_temperature
            attributes["outside_temperature_unit"] = self._unit_of_measurement

        if self.room_humidity is not None:
            attributes["room_humidity"] = self.room_humidity
            attributes["room_humidity_unit"] = "%"

        return attributes if attributes else None

    async def async_set_temperature(self, **kwargs):
        """Set new target temperature."""
        target_temperature = kwargs.get(ATTR_TEMPERATURE)
        if target_temperature is not None:
            # Explicit setpoint change while eco shutoff is holding the unit off — user
            # is taking control back, so clear eco and restore power before applying.
            if self._eco_shutoff_active:
                self._eco_shutoff_active = False
                self._eco_shutoff_satisfied_since = None
                await self._save_persistent_state()
                signal = f"{DOMAIN}_{self._mac_addr}_eco_shutoff_update"
                async_dispatcher_send(self.hass, signal, False)
                await self.SyncState({"Pow": 1})

            # do nothing if temperature is none
            if not (self._acOptions["Pow"] == 0):
                # do nothing if HVAC is switched off

                if self._unit_of_measurement == "°C":
                    SetTem, TemRec = encode_temp_c(T=target_temperature)  # takes care of 1/2 degrees
                elif self._unit_of_measurement == "°F":
                    SetTem, TemRec = gree_f_to_c(desired_temp_f=target_temperature)
                else:
                    _LOGGER.error("Unable to set temperature. Units not set to °C or °F")
                    return

                await self.SyncState({"SetTem": int(SetTem), "TemRec": int(TemRec)})
                _LOGGER.debug(f"{self._name}: async_set_temperature: Set Temp to {target_temperature}{self._unit_of_measurement} ->  SyncState with SetTem={SetTem}, SyncState with TemRec={TemRec}")

                # Mark as manual override - user has taken control of temperature
                # But not if we're applying a preset temperature programmatically
                if not getattr(self, '_applying_preset', False):
                    self._set_manual_override(True)
                    _LOGGER.info(f"{self._name}: Manual override activated - temperature set to {target_temperature}{self._unit_of_measurement}")

                self.async_write_ha_state()

    async def async_set_swing_mode(self, swing_mode):
        """Set swing mode."""
        if not (self._acOptions["Pow"] == 0):
            # do nothing if HVAC is switched off
            try:
                sw_up_dn = MODES_MAPPING.get("SwUpDn").get(swing_mode)
                _LOGGER.info(f"{self._name}: SyncState with SwUpDn={sw_up_dn}")
                await self.SyncState({"SwUpDn": sw_up_dn})
                self.async_write_ha_state()
            except ValueError:
                _LOGGER.error(f"Unknown swing mode: {swing_mode}")
                return

    async def async_set_swing_horizontal_mode(self, swing_horizontal_mode):
        """Set horizontal swing mode."""
        if not (self._acOptions["Pow"] == 0):
            # do nothing if HVAC is switched off
            try:
                swing_lf_rig = MODES_MAPPING.get("SwingLfRig").get(swing_horizontal_mode)
                _LOGGER.info(f"{self._name}: SyncState with SwingLfRig={swing_lf_rig}")
                await self.SyncState({"SwingLfRig": swing_lf_rig})
                self.async_write_ha_state()
            except ValueError:
                _LOGGER.error(f"Unknown preset mode: {swing_horizontal_mode}")
                return

    async def async_set_fan_mode(self, fan):
        """Set fan mode."""
        # Set the fan mode.
        if not (self._acOptions["Pow"] == 0):
            try:
                wd_spd = MODES_MAPPING.get("WdSpd").get(fan)

                # Check if this is turbo mode
                if fan == "turbo":
                    _LOGGER.info("Enabling turbo mode")
                    await self.SyncState({"Tur": 1, "Quiet": 0})
                # Check if this is quiet mode
                elif fan == "quiet":
                    _LOGGER.info("Enabling quiet mode")
                    await self.SyncState({"Tur": 0, "Quiet": 1})
                else:
                    _LOGGER.info(f"{self._name}: Setting normal fan mode to {wd_spd}")
                    await self.SyncState({"WdSpd": str(wd_spd), "Tur": 0, "Quiet": 0})

                self.async_write_ha_state()
            except ValueError:
                _LOGGER.error(f"Unknown fan mode: {fan}")
                return

    async def async_set_hvac_mode(self, hvac_mode):
        """Set new operation mode."""
        _LOGGER.info(f"{self._name}: async_set_hvac_mode(): {hvac_mode}")

        # Track last non-Auto mode for smart fallback
        if hvac_mode in (HVACMode.HEAT, HVACMode.COOL):
            self._last_non_auto_hvac_mode = hvac_mode

        c = {}
        if hvac_mode == HVACMode.OFF:
            c.update({"Pow": 0})
            if hasattr(self, "_auto_light") and self._auto_light:
                c.update({"Lig": 0})
        else:
            mod = MODES_MAPPING.get("Mod").get(hvac_mode)
            c.update({"Pow": 1, "Mod": mod})
            if hasattr(self, "_auto_light") and self._auto_light:
                c.update({"Lig": 1})
            if hasattr(self, "_auto_xfan") and self._auto_xfan:
                if (hvac_mode == HVACMode.COOL) or (hvac_mode == HVACMode.DRY):
                    c.update({"Blo": 1})
        await self.SyncState(c)
        await self._save_persistent_state()

        # If we have an active preset, apply its temp for the new mode
        if self._preset_mode != PRESET_NONE:
            await self._apply_preset_temperature()

        self.async_write_ha_state()

    async def _apply_preset_temperature(self):
        """Apply temperature based on current preset and hvac_mode."""
        if self._preset_mode == PRESET_NONE or self._preset_mode == PRESET_OFF:
            return

        # Smart 8°C mode controls the temperature — don't override it with preset temp
        if self._stht_smart_active:
            _LOGGER.debug(f"{self._name}: Skipping preset temp apply — smart 8°C mode is active")
            return

        temps = self._preset_temps[self._preset_mode]

        # Determine which temp to use based on current hvac_mode
        if self.hvac_mode == HVACMode.HEAT:
            target_c = temps["heat"]
        elif self.hvac_mode == HVACMode.COOL:
            target_c = temps["cool"]
        else:
            # Don't change temp for dry/fan_only modes
            return

        # Convert to user's display units if needed
        if self._unit_of_measurement == UnitOfTemperature.FAHRENHEIT:
            # Simple C to F conversion for display
            target = round((target_c * 9.0 / 5.0) + 32.0)
        else:
            target = target_c

        _LOGGER.info(f"{self._name}: Applying preset {self._preset_mode} temp: {target}{self._unit_of_measurement}")

        # Set flag to prevent this from triggering manual override
        self._applying_preset = True
        await self.async_set_temperature(temperature=target)
        self._applying_preset = False

    async def _check_eco_shutoff(self):
        """Eco Shutoff state machine — runs every poll cycle."""
        if not self._eco_shutoff_enabled or not self._eco_shutoff_sensor:
            if self._eco_shutoff_active:
                # Stale active flag (feature disabled or sensor removed after a firing) —
                # clear it now so the Store and UI stay consistent across reloads.
                self._eco_shutoff_active = False
                self._eco_shutoff_satisfied_since = None
                await self._save_persistent_state()
                signal = f"{DOMAIN}_{self._mac_addr}_eco_shutoff_update"
                async_dispatcher_send(self.hass, signal, False)
            return
        if self.hvac_mode not in (HVACMode.HEAT, HVACMode.COOL):
            return
        if self._preset_mode in (PRESET_NONE, PRESET_OFF):
            return

        # --- Sensor availability check ---
        sensor_state = self.hass.states.get(self._eco_shutoff_sensor)
        sensor_stale = False
        if sensor_state is not None and sensor_state.state not in ("unavailable", "unknown"):
            last_reported = getattr(sensor_state, "last_reported", sensor_state.last_updated)
            age_s = (dt_util.utcnow() - last_reported).total_seconds()
            if age_s > ECO_SHUTOFF_SENSOR_STALE_S:
                sensor_stale = True
                _LOGGER.warning(
                    f"{self._name}: Eco Shutoff sensor last reported {age_s / 60:.0f} min ago — treating as stale"
                )
        if sensor_state is None or sensor_state.state in ("unavailable", "unknown") or sensor_stale:
            self._eco_shutoff_satisfied_since = None
            self._eco_shutoff_sensor_missing_s += SCAN_INTERVAL.total_seconds()
            if self._eco_shutoff_sensor_missing_s >= ECO_SHUTOFF_SENSOR_TIMEOUT_S:
                if self._eco_shutoff_enabled:
                    ir.async_create_issue(
                        self.hass,
                        DOMAIN,
                        f"eco_shutoff_sensor_{self._mac_addr}",
                        is_fixable=False,
                        severity=ir.IssueSeverity.WARNING,
                        translation_key="eco_shutoff_sensor_unavailable",
                        translation_placeholders={
                            "device_name": self._name,
                            "sensor_id": self._eco_shutoff_sensor or "",
                        },
                    )
                if self._eco_shutoff_active:
                    _LOGGER.warning(
                        f"{self._name}: Eco Shutoff sensor unavailable for "
                        f"{self._eco_shutoff_sensor_missing_s:.0f}s — restoring power"
                    )
                    await self.SyncState({"Pow": 1})
                    self._eco_shutoff_active = False
                    await self._save_persistent_state()
                    signal = f"{DOMAIN}_{self._mac_addr}_eco_shutoff_update"
                    async_dispatcher_send(self.hass, signal, False)
            return

        # Sensor is healthy — clear any outstanding repair issue and reset counter
        self._eco_shutoff_sensor_missing_s = 0
        ir.async_delete_issue(self.hass, DOMAIN, f"eco_shutoff_sensor_{self._mac_addr}")

        # --- Read auxiliary temperature in °C ---
        try:
            aux_temp = float(sensor_state.state)
        except (ValueError, TypeError):
            return
        sensor_unit = sensor_state.attributes.get("unit_of_measurement", UnitOfTemperature.CELSIUS)
        if sensor_unit not in TemperatureConverter.VALID_UNITS:
            _LOGGER.warning(f"{self._name}: Eco Shutoff sensor has unsupported unit {sensor_unit!r}, skipping")
            return
        aux_temp = TemperatureConverter.convert(aux_temp, sensor_unit, UnitOfTemperature.CELSIUS)

        # --- Effective setpoint in °C (_target_temperature is in the display unit) ---
        if self._stht_smart_active:
            effective_setpoint = 8.0
        else:
            if self._target_temperature is None:
                return
            effective_setpoint = TemperatureConverter.convert(
                self._target_temperature, self._unit_of_measurement, UnitOfTemperature.CELSIUS
            )

        # --- Satisfaction and re-engage thresholds ---
        if self.hvac_mode == HVACMode.HEAT:
            satisfied = aux_temp >= (effective_setpoint + self._eco_shutoff_satisfied_margin)
            needs_action = aux_temp <= (effective_setpoint - self._eco_shutoff_reengage_delta)
        else:  # COOL
            satisfied = aux_temp <= (effective_setpoint - self._eco_shutoff_satisfied_margin)
            needs_action = aux_temp >= (effective_setpoint + self._eco_shutoff_reengage_delta)

        # --- Time-based satisfaction window for shutoff ---
        now = dt_util.utcnow()
        if satisfied:
            if self._eco_shutoff_satisfied_since is None:
                self._eco_shutoff_satisfied_since = now
            elapsed_s = (now - self._eco_shutoff_satisfied_since).total_seconds()
            time_confirmed = elapsed_s >= self._eco_shutoff_trend_window_minutes * 60
        else:
            self._eco_shutoff_satisfied_since = None
            time_confirmed = False

        is_on = self._acOptions and self._acOptions.get("Pow") == 1

        if not self._eco_shutoff_active:
            if is_on and satisfied and time_confirmed:
                _LOGGER.info(
                    f"{self._name}: Eco Shutoff — satisfied by {aux_temp:.1f}°C "
                    f"(setpoint {effective_setpoint:.1f}+{self._eco_shutoff_satisfied_margin}°C) "
                    f"for {elapsed_s / 60:.1f} min, cutting power"
                )
                self._eco_shutoff_active = True
                await self.SyncState({"Pow": 0})
                await self._save_persistent_state()
                signal = f"{DOMAIN}_{self._mac_addr}_eco_shutoff_update"
                async_dispatcher_send(self.hass, signal, True)
        else:
            if needs_action:
                _LOGGER.info(
                    f"{self._name}: Eco Shutoff — temp {aux_temp:.1f}°C drifted within "
                    f"{self._eco_shutoff_reengage_delta}°C of setpoint {effective_setpoint:.1f}°C, restoring power"
                )
                await self.SyncState({"Pow": 1})
                self._eco_shutoff_active = False
                await self._save_persistent_state()
                signal = f"{DOMAIN}_{self._mac_addr}_eco_shutoff_update"
                async_dispatcher_send(self.hass, signal, False)

    async def _manage_stht_auto(self):
        """Auto-activate 8°C frost protection for away/sleep heat presets after threshold."""
        if not self._stht_smart_enabled:
            return

        # Only care about preset and mode — not device power state.
        # We count wall-clock time from when the preset was set, not compressor runtime.
        in_eligible_preset = (
            self._preset_mode in (PRESET_AWAY, PRESET_SLEEP)
            and self.hvac_mode == HVACMode.HEAT
        )

        if self._stht_smart_active:
            if not in_eligible_preset:
                _LOGGER.info(f"{self._name}: Preset/mode changed - deactivating smart 8°C mode")
                self._stht_smart_active = False
                await self.SyncState({"StHt": 0})
                await self._save_persistent_state()
            elif self._acOptions.get("StHt") != 1:
                # Device cleared StHt (firmware behaviour) — re-apply to maintain frost protection
                _LOGGER.info(f"{self._name}: StHt cleared by device - re-applying smart 8°C")
                await self.SyncState({"StHt": 1})
            return

        if not in_eligible_preset:
            if self._preset_active_since is not None:
                self._preset_active_since = None
            return

        if self._preset_active_since is None:
            self._preset_active_since = datetime.now()
            _LOGGER.info(f"{self._name}: Smart 8°C timer started for {self._preset_mode}+heat preset")
            await self._save_persistent_state()

        # Don't interfere if user manually turned StHt on
        if self._acOptions.get("StHt") == 1:
            return

        elapsed = (datetime.now() - self._preset_active_since).total_seconds()
        threshold = self._stht_smart_threshold_minutes * 60
        if elapsed >= threshold:
            _LOGGER.info(f"{self._name}: Smart 8°C activating after {elapsed / 60:.1f}min in {self._preset_mode}+heat")
            self._stht_smart_active = True
            await self.SyncState({"StHt": 1})
            await self._save_persistent_state()
        else:
            remaining = (threshold - elapsed) / 60
            _LOGGER.debug(f"{self._name}: Smart 8°C timer: {elapsed / 60:.1f}min elapsed, {remaining:.1f}min remaining")

    async def _save_persistent_state(self):
        """Save all persistent state to storage in one call."""
        last_mode_str = (
            self._last_non_auto_hvac_mode.value
            if isinstance(self._last_non_auto_hvac_mode, HVACMode)
            else self._last_non_auto_hvac_mode
        )
        await self._storage.async_save({
            "preset_mode": self._preset_mode,
            "last_non_auto_hvac_mode": last_mode_str,
            "preset_active_since": self._preset_active_since.isoformat() if self._preset_active_since else None,
            "stht_smart_active": self._stht_smart_active,
            "scheduled_preset": self._scheduled_preset,
            "eco_shutoff_active": self._eco_shutoff_active,
        })

    async def async_set_preset_mode(self, preset_mode):
        """Set preset mode and apply appropriate temperature or turn off."""
        _LOGGER.info(f"{self._name}: async_set_preset_mode(): {preset_mode}")
        self._preset_mode = preset_mode

        # Clear manual override when changing presets
        if self._manual_override:
            _LOGGER.info(f"{self._name}: Clearing manual override due to preset change")
        self._set_manual_override(False)

        # Deactivate smart 8°C mode immediately on preset change
        if self._stht_smart_active:
            _LOGGER.info(f"{self._name}: Preset changed to {preset_mode} - deactivating smart 8°C mode")
            self._stht_smart_active = False
            await self.SyncState({"StHt": 0})
        self._preset_active_since = None

        # Persist all state
        await self._save_persistent_state()

        # Notify select entity of preset mode change
        signal = f"{DOMAIN}_{self._mac_addr}_preset_mode_update"
        async_dispatcher_send(self.hass, signal, preset_mode)

        # Handle preset actions
        if preset_mode == PRESET_OFF:
            await self.async_set_hvac_mode(HVACMode.OFF)
        elif preset_mode != PRESET_NONE:
            await self._apply_preset_temperature()

        self.async_write_ha_state()

    async def set_scheduled_preset(self, preset_mode: str) -> None:
        """Store the scheduled preset. Apply immediately unless overridden or away."""
        _LOGGER.info(f"{self._name}: Scheduled preset set to {preset_mode}")
        self._scheduled_preset = preset_mode
        await self._save_persistent_state()

        if self._manual_override:
            if self._schedule_auto_release:
                _LOGGER.info(
                    f"{self._name}: Manual override active but schedule_auto_release is on — "
                    f"auto-releasing override and applying scheduled preset '{preset_mode}'"
                )
                await self.async_resume_normal()
                return
            _LOGGER.info(f"{self._name}: Manual override active — storing scheduled preset without applying")
            self.async_write_ha_state()
            return

        if self._preset_mode == PRESET_AWAY:
            _LOGGER.info(f"{self._name}: Away mode active — storing scheduled preset without applying")
            self.async_write_ha_state()
            return

        await self.async_set_preset_mode(preset_mode)

    async def async_resume_normal(self) -> None:
        """Resume the scheduled preset, clearing any manual override or away mode."""
        _LOGGER.info(f"{self._name}: Resuming normal schedule")

        target_preset = self._scheduled_preset or self._preset_mode
        if target_preset in (PRESET_NONE, PRESET_OFF):
            return

        # If in Auto mode, switch to last non-Auto mode so preset temp can be applied
        if self.hvac_mode == HVACMode.AUTO:
            target_mode = self._last_non_auto_hvac_mode
            _LOGGER.info(f"{self._name}: Switching from Auto to {target_mode} to apply preset")
            await self.async_set_hvac_mode(target_mode)

        # async_set_preset_mode clears manual_override, deactivates smart 8°C,
        # applies the preset temperature, and saves state
        await self.async_set_preset_mode(target_preset)

    def _set_manual_override(self, value: bool):
        """Set manual override and notify listeners."""
        self._manual_override = value
        # Notify binary sensor to update
        signal = f"{DOMAIN}_{self._mac_addr}_manual_override_update"
        async_dispatcher_send(self.hass, signal, value)

    async def async_turn_on(self):
        """Turn on."""
        _LOGGER.info("async_turn_on(): ")
        # Turn on.
        c = {"Pow": 1}
        if hasattr(self, "_auto_light") and self._auto_light:
            c.update({"Lig": 1})
        await self.SyncState(c)
        self.async_write_ha_state()

    async def async_turn_off(self):
        """Turn off."""
        _LOGGER.info("async_turn_off(): ")
        # Turn off.
        c = {"Pow": 0}
        if hasattr(self, "_auto_light") and self._auto_light:
            c.update({"Lig": 0})
        await self.SyncState(c)
        self.async_write_ha_state()

    async def async_added_to_hass(self):
        """Restore preset mode when entity added to hass."""
        _LOGGER.info("Gree climate device added to hass()")

        # Restore preset mode and last non-auto HVAC mode
        data = await self._storage.async_load()
        if data:
            self._preset_mode = data.get("preset_mode", PRESET_NONE)
            _LOGGER.info(f"{self._name}: Restored preset mode: {self._preset_mode}")

            # Restore last non-auto mode (for Auto fallback)
            last_mode_str = data.get("last_non_auto_hvac_mode")
            if last_mode_str:
                self._last_non_auto_hvac_mode = HVACMode(last_mode_str)
                _LOGGER.info(f"{self._name}: Restored last non-auto mode: {self._last_non_auto_hvac_mode}")

            # Restore smart 8°C mode state
            self._stht_smart_active = data.get("stht_smart_active", False)
            preset_active_since_str = data.get("preset_active_since")
            if preset_active_since_str:
                try:
                    self._preset_active_since = datetime.fromisoformat(preset_active_since_str)
                except (ValueError, TypeError):
                    self._preset_active_since = None
            _LOGGER.info(f"{self._name}: Restored smart 8°C state: active={self._stht_smart_active}, timer_start={self._preset_active_since}")

            self._scheduled_preset = data.get("scheduled_preset")
            _LOGGER.info(f"{self._name}: Restored scheduled preset: {self._scheduled_preset}")

            self._eco_shutoff_active = data.get("eco_shutoff_active", False)
            _LOGGER.info(f"{self._name}: Restored eco_shutoff_active: {self._eco_shutoff_active}")
            if self._eco_shutoff_active and self._last_non_auto_hvac_mode not in (HVACMode.OFF, None):
                # Eco shutoff was holding the unit off at shutdown; prime hvac_mode so the
                # mode guard in _check_eco_shutoff passes on first poll and re-engage can run.
                self._hvac_mode = self._last_non_auto_hvac_mode
                _LOGGER.info(f"{self._name}: Primed hvac_mode to {self._hvac_mode} for eco shutoff re-evaluate")

        # Fetch current device state (reads temp, mode, etc. from physical unit)
        await self.async_update()

        # Recalculate manual override by comparing device temp with expected preset temp
        self._recalculate_manual_override()

    def _recalculate_manual_override(self):
        """Recalculate manual override based on device temp vs expected preset temp."""
        if self._preset_mode in (PRESET_NONE, PRESET_OFF):
            # No active preset, so no override possible
            self._manual_override = False
            _LOGGER.debug(f"{self._name}: No active preset - manual override = False")
            return

        # If smart mode activated StHt, it's not a manual override — skip detection
        # If the user manually toggled StHt on, treat it as a manual override (temp = 8°C by choice)
        if self._acOptions and self._acOptions.get("StHt") == 1:
            if self._stht_smart_active:
                self._manual_override = False
                _LOGGER.debug(f"{self._name}: Smart 8°C active - manual override detection skipped")
            else:
                self._manual_override = True
                _LOGGER.debug(f"{self._name}: User-activated 8°C mode - treating as manual override")
            return

        # Auto mode is always considered manual override (doesn't fit preset system)
        if self.hvac_mode == HVACMode.AUTO:
            if not self._manual_override:  # Only log on state change
                _LOGGER.info(f"{self._name}: Auto mode detected - setting manual override")
            self._manual_override = True
            return

        # Get expected temperature for current preset + HVAC mode
        expected_temp_c = self._get_expected_preset_temp_c()
        if expected_temp_c is None:
            # Can't determine (e.g., dry/fan mode, or preset temps not loaded yet)
            self._manual_override = False
            _LOGGER.debug(f"{self._name}: Can't determine expected temp - manual override = False")
            return

        # Get current device temperature in Celsius
        current_temp = self._target_temperature
        if current_temp is None:
            self._manual_override = False
            _LOGGER.debug(f"{self._name}: No current temp - manual override = False")
            return

        # Convert to Celsius if needed for comparison
        if self._unit_of_measurement == UnitOfTemperature.FAHRENHEIT:
            current_temp_c = (current_temp - 32.0) * 5.0 / 9.0
        else:
            current_temp_c = current_temp

        # Compare (allow small tolerance for rounding)
        temp_diff = abs(current_temp_c - expected_temp_c)
        if temp_diff > 0.2:  # More than 0.2°C difference
            self._manual_override = True
            _LOGGER.info(f"{self._name}: Manual override detected on startup - Device: {current_temp_c:.1f}°C, Expected: {expected_temp_c:.1f}°C (diff: {temp_diff:.2f}°C)")
        else:
            self._manual_override = False
            _LOGGER.debug(f"{self._name}: Temp matches preset - manual override = False")

    def _get_expected_preset_temp_c(self):
        """Get expected Celsius temperature for current preset + HVAC mode."""
        if self._preset_mode not in self._preset_temps:
            return None

        temps = self._preset_temps[self._preset_mode]

        if self.hvac_mode == HVACMode.HEAT:
            return temps["heat"]
        elif self.hvac_mode == HVACMode.COOL:
            return temps["cool"]
        else:
            return None  # No preset temp for dry/fan modes

    async def async_will_remove_from_hass(self) -> None:
        """Clean up when entity is removed."""
        for name, entity_id, unsub in self._listeners:
            _LOGGER.debug("Deregistering %s listener for %s", name, entity_id)
            unsub()
        self._listeners.clear()
