import logging
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError
from urllib.parse import urlparse
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    DOMAIN, CONF_HOST, CONF_USERNAME, CONF_PASSWORD, CONF_API_KEY, CONF_ENDPOINT_ID,
    CONF_SSL_VERIFY, CONF_TIMEOUT, CONF_UPDATE_INTERVAL, CONF_CACHE_DURATION,
    CONF_RATE_LIMIT_CHECKS, CONF_RATE_LIMIT_PERIOD, CONF_ENABLE_UPDATE_CHECKS,
    CONF_ENABLE_HEALTH_MONITORING, CONF_ENABLE_RESOURCE_MONITORING,
    CONF_INTEGRATION_MODE, CONF_ENABLE_STACK_VIEW, CONF_ENABLE_CONTAINER_LOGS,
    CONF_ENABLE_RESOURCE_SENSORS, CONF_ENABLE_VERSION_SENSORS, CONF_ENABLE_UPDATE_SENSORS,
    CONF_ENABLE_STACK_BUTTONS, CONF_ENABLE_CONTAINER_BUTTONS, CONF_ENABLE_BULK_OPERATIONS,
    DEFAULT_SSL_VERIFY, DEFAULT_TIMEOUT, DEFAULT_UPDATE_INTERVAL,
    DEFAULT_CACHE_DURATION, DEFAULT_RATE_LIMIT_CHECKS, DEFAULT_RATE_LIMIT_PERIOD,
    DEFAULT_ENABLE_UPDATE_CHECKS, DEFAULT_ENABLE_HEALTH_MONITORING, DEFAULT_ENABLE_RESOURCE_MONITORING,
    DEFAULT_INTEGRATION_MODE, DEFAULT_ENABLE_STACK_VIEW, DEFAULT_ENABLE_CONTAINER_LOGS,
    DEFAULT_ENABLE_RESOURCE_SENSORS, DEFAULT_ENABLE_VERSION_SENSORS, DEFAULT_ENABLE_UPDATE_SENSORS,
    DEFAULT_ENABLE_STACK_BUTTONS, DEFAULT_ENABLE_CONTAINER_BUTTONS, DEFAULT_ENABLE_BULK_OPERATIONS,
    MIN_UPDATE_INTERVAL, MAX_UPDATE_INTERVAL, MIN_CACHE_DURATION, MAX_CACHE_DURATION,
    MIN_RATE_LIMIT_CHECKS, MAX_RATE_LIMIT_CHECKS,
    INTEGRATION_MODE_LIGHTWEIGHT, INTEGRATION_MODE_STANDARD, INTEGRATION_MODE_FULL, INTEGRATION_MODE_CUSTOM,
    INTEGRATION_MODE_PRESETS
)
from .portainer_api import PortainerAPI

_LOGGER = logging.getLogger(__name__)

class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""

class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""

class PortainerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 3

    def __init__(self):
        """Initialize the config flow."""
        super().__init__()
        self.config_data = {}

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the initial step - basic connection settings."""
        errors = {}

        if user_input is not None:
            # Store the basic configuration
            self.config_data.update(user_input)
            
            # Process and validate the basic configuration
            try:
                processed_config = await self._process_basic_config(user_input)
                await self._validate_basic_config(processed_config)
                
                # Move to integration mode selection
                return await self.async_step_integration_mode()
                
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except ValueError as e:
                errors["base"] = "invalid_config"
                _LOGGER.error("Configuration error: %s", e)
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        data_schema = vol.Schema({
            vol.Required(CONF_HOST, description="Full Portainer URL including protocol and port"): str,
            vol.Optional(CONF_USERNAME, description="Portainer username (leave empty if using API key)"): str,
            vol.Optional(CONF_PASSWORD, description="Portainer password (leave empty if using API key)"): str,
            vol.Optional(CONF_API_KEY, description="Portainer API key (alternative to username/password)"): str,
            vol.Required(CONF_ENDPOINT_ID, default=1, description="Docker endpoint ID (usually 1 for single Docker host)"): int,
            vol.Optional(CONF_TIMEOUT, default=DEFAULT_TIMEOUT, description="Request timeout in seconds (default: 30)"): int,
        })

        return self.async_show_form(
            step_id="user", 
            data_schema=data_schema, 
            errors=errors,
            description_placeholders={
                "examples": """
**Examples:**
- **HTTPS with custom port:** `https://192.168.1.100:9443`
- **HTTP with default port:** `http://192.168.1.100:9000`
- **Local network:** `https://portainer.local:9443`
- **With domain:** `https://portainer.mydomain.com`

**Authentication Options:**
- **Username/Password:** Enter your Portainer login credentials
- **API Key:** Generate in Portainer → Settings → API Keys
- **Endpoint ID:** Usually 1 for single Docker host, check Portainer → Endpoints
                """
            }
        )

    async def async_step_integration_mode(self, user_input=None) -> FlowResult:
        """Handle integration mode selection."""
        if user_input is not None:
            self.config_data.update(user_input)
            
            # Apply preset configuration based on selected mode
            selected_mode = user_input[CONF_INTEGRATION_MODE]
            if selected_mode != INTEGRATION_MODE_CUSTOM:
                preset_config = INTEGRATION_MODE_PRESETS[selected_mode]["features"]
                self.config_data.update(preset_config)
            
            # If custom mode, move to feature selection
            if selected_mode == INTEGRATION_MODE_CUSTOM:
                return await self.async_step_custom_features()
            else:
                # Apply preset and create entry
                return await self._create_entry()

        # Show integration mode options
        mode_options = {
            INTEGRATION_MODE_LIGHTWEIGHT: f"Lightweight - {INTEGRATION_MODE_PRESETS[INTEGRATION_MODE_LIGHTWEIGHT]['description']}",
            INTEGRATION_MODE_STANDARD: f"Standard - {INTEGRATION_MODE_PRESETS[INTEGRATION_MODE_STANDARD]['description']}",
            INTEGRATION_MODE_FULL: f"Full - {INTEGRATION_MODE_PRESETS[INTEGRATION_MODE_FULL]['description']}",
            INTEGRATION_MODE_CUSTOM: "Custom - Choose your own features"
        }

        data_schema = vol.Schema({
            vol.Required(CONF_INTEGRATION_MODE, default=DEFAULT_INTEGRATION_MODE, description="Choose how much functionality you want"): vol.In(mode_options)
        })

        return self.async_show_form(
            step_id="integration_mode",
            data_schema=data_schema,
            description_placeholders={
                "lightweight_desc": INTEGRATION_MODE_PRESETS[INTEGRATION_MODE_LIGHTWEIGHT]["description"],
                "standard_desc": INTEGRATION_MODE_PRESETS[INTEGRATION_MODE_STANDARD]["description"],
                "full_desc": INTEGRATION_MODE_PRESETS[INTEGRATION_MODE_FULL]["description"],
                "mode_help": """
**Integration Modes:**

**Lightweight** - Minimal resource usage
- Container status sensors
- Start/stop switches
- 10-minute updates
- Perfect for performance-sensitive environments

**Standard** - Balanced functionality  
- Stack view and management
- Resource monitoring (CPU, memory, uptime)
- Version tracking and update checks
- 5-minute updates
- Recommended for most users

**Full** - Complete functionality
- Everything including container logs
- Bulk operations
- Advanced monitoring
- 3-minute updates
- For power users who want everything

**Custom** - Choose your own features
- Granular control over every feature
- Configurable update intervals
- Perfect for advanced users
                """
            }
        )

    async def async_step_custom_features(self, user_input=None) -> FlowResult:
        """Handle custom feature selection."""
        if user_input is not None:
            self.config_data.update(user_input)
            return await self._create_entry()

        # Show custom feature options
        data_schema = vol.Schema({
            vol.Optional(CONF_ENABLE_STACK_VIEW, default=DEFAULT_ENABLE_STACK_VIEW, description="Enable stack clustering and management features"): bool,
            vol.Optional(CONF_ENABLE_CONTAINER_LOGS, default=DEFAULT_ENABLE_CONTAINER_LOGS, description="Enable container log viewing (requires Full mode)"): bool,
            vol.Optional(CONF_ENABLE_RESOURCE_SENSORS, default=DEFAULT_ENABLE_RESOURCE_SENSORS, description="Enable CPU, memory, and uptime monitoring sensors"): bool,
            vol.Optional(CONF_ENABLE_VERSION_SENSORS, default=DEFAULT_ENABLE_VERSION_SENSORS, description="Enable current and available version tracking"): bool,
            vol.Optional(CONF_ENABLE_UPDATE_SENSORS, default=DEFAULT_ENABLE_UPDATE_SENSORS, description="Enable update availability detection (rate-limited)"): bool,
            vol.Optional(CONF_ENABLE_STACK_BUTTONS, default=DEFAULT_ENABLE_STACK_BUTTONS, description="Enable stack start/stop/update buttons"): bool,
            vol.Optional(CONF_ENABLE_CONTAINER_BUTTONS, default=DEFAULT_ENABLE_CONTAINER_BUTTONS, description="Enable container restart and pull update buttons"): bool,
            vol.Optional(CONF_ENABLE_BULK_OPERATIONS, default=DEFAULT_ENABLE_BULK_OPERATIONS, description="Enable bulk start/stop all containers buttons"): bool,
            vol.Optional(CONF_UPDATE_INTERVAL, default=DEFAULT_UPDATE_INTERVAL, description=f"Update interval in minutes ({MIN_UPDATE_INTERVAL}-{MAX_UPDATE_INTERVAL})"): vol.All(vol.Coerce(int), vol.Range(min=MIN_UPDATE_INTERVAL, max=MAX_UPDATE_INTERVAL)),
        })

        return self.async_show_form(
            step_id="custom_features",
            data_schema=data_schema,
            description_placeholders={
                "feature_help": """
**Custom Feature Configuration:**

**Core Features (Always Available):**
- Container status sensors
- Container start/stop switches

**Optional Features:**
- **Stack View:** Group containers by Docker Compose stacks
- **Resource Sensors:** Monitor CPU, memory, and uptime
- **Version Sensors:** Track current and available versions
- **Update Sensors:** Check for available updates (rate-limited)
- **Stack Buttons:** Control entire stacks at once
- **Container Buttons:** Restart containers and pull updates
- **Bulk Operations:** Start/stop all containers with one button

**Update Interval:** How often to refresh data (1-60 minutes)
- Lower values = more responsive but higher resource usage
- Higher values = less responsive but lower resource usage
                """
            }
        )

    async def _create_entry(self) -> FlowResult:
        """Create the config entry."""
        try:
            # Process and validate the complete configuration
            processed_config = await self._process_complete_config(self.config_data)
            await self._validate_complete_config(processed_config)
            
            # Create the entry
            return self.async_create_entry(
                title=f"Portainer ({processed_config['host']}) - {processed_config.get(CONF_INTEGRATION_MODE, 'full').title()}", 
                data=processed_config
            )
        except Exception as e:
            _LOGGER.exception("Failed to create config entry: %s", e)
            return self.async_abort(reason="config_error")

    async def _process_basic_config(self, user_input: dict) -> dict:
        """Process and normalize the basic configuration."""
        config = user_input.copy()
        
        # Process host URL - user should provide full URL
        host = config[CONF_HOST].strip()
        
        # Validate and normalize the URL
        if not host.startswith(("http://", "https://")):
            # If user didn't provide scheme, default to https
            host = f"https://{host}"
            _LOGGER.info("🔧 Added https:// scheme to host URL: %s", host)
        
        # Ensure the URL is properly formatted
        config[CONF_HOST] = host.rstrip("/")
        
        _LOGGER.debug("🔧 Processed host URL: %s", config[CONF_HOST])
        
        return config

    async def _process_complete_config(self, config: dict) -> dict:
        """Process and normalize the complete configuration."""
        # Set defaults for advanced options
        config.setdefault(CONF_CACHE_DURATION, DEFAULT_CACHE_DURATION)
        config.setdefault(CONF_RATE_LIMIT_CHECKS, DEFAULT_RATE_LIMIT_CHECKS)
        config.setdefault(CONF_RATE_LIMIT_PERIOD, DEFAULT_RATE_LIMIT_PERIOD)
        config.setdefault(CONF_ENABLE_UPDATE_CHECKS, DEFAULT_ENABLE_UPDATE_CHECKS)
        config.setdefault(CONF_ENABLE_HEALTH_MONITORING, DEFAULT_ENABLE_HEALTH_MONITORING)
        config.setdefault(CONF_ENABLE_RESOURCE_MONITORING, DEFAULT_ENABLE_RESOURCE_MONITORING)
        
        return config

    async def _validate_basic_config(self, config: dict) -> None:
        """Validate the basic configuration."""
        host = config[CONF_HOST]
        username = config.get(CONF_USERNAME)
        password = config.get(CONF_PASSWORD)
        api_key = config.get(CONF_API_KEY)
        endpoint_id = config[CONF_ENDPOINT_ID]

        # Validate host URL
        if not host.startswith(("http://", "https://")):
            raise ValueError("Host must be a valid URL")

        # Validate authentication
        if not api_key and (not username or not password):
            raise InvalidAuth("Either API key or username/password must be provided")

        # Validate endpoint ID
        if not isinstance(endpoint_id, int) or endpoint_id < 1:
            raise ValueError("Endpoint ID must be a positive integer")

        # Test connection
        try:
            api = PortainerAPI(host, username, password, api_key, config=config)
            if not await api.initialize():
                raise CannotConnect("Failed to initialize connection to Portainer")
            
            # Test getting containers to verify endpoint access
            containers = await api.get_containers(endpoint_id)
            if containers is None:
                raise CannotConnect("Failed to access Docker endpoint")
                
            await api.close()
            
        except Exception as e:
            _LOGGER.error("Configuration validation failed: %s", e)
            if "authentication" in str(e).lower() or "unauthorized" in str(e).lower():
                raise InvalidAuth("Authentication failed")
            else:
                raise CannotConnect(f"Connection failed: {e}")

    async def _validate_complete_config(self, config: dict) -> None:
        """Validate the complete configuration."""
        update_interval = config.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
        cache_duration = config.get(CONF_CACHE_DURATION, DEFAULT_CACHE_DURATION)
        rate_limit_checks = config.get(CONF_RATE_LIMIT_CHECKS, DEFAULT_RATE_LIMIT_CHECKS)
        rate_limit_period = config.get(CONF_RATE_LIMIT_PERIOD, DEFAULT_RATE_LIMIT_PERIOD)

        # Validate advanced settings
        if not MIN_UPDATE_INTERVAL <= update_interval <= MAX_UPDATE_INTERVAL:
            raise ValueError(f"Update interval must be between {MIN_UPDATE_INTERVAL} and {MAX_UPDATE_INTERVAL} minutes")
        
        if not MIN_CACHE_DURATION <= cache_duration <= MAX_CACHE_DURATION:
            raise ValueError(f"Cache duration must be between {MIN_CACHE_DURATION} and {MAX_CACHE_DURATION} hours")
        
        if not MIN_RATE_LIMIT_CHECKS <= rate_limit_checks <= MAX_RATE_LIMIT_CHECKS:
            raise ValueError(f"Rate limit checks must be between {MIN_RATE_LIMIT_CHECKS} and {MAX_RATE_LIMIT_CHECKS}")
        
        if not 1 <= rate_limit_period <= 24:
            raise ValueError("Rate limit period must be between 1 and 24 hours")

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return PortainerOptionsFlowHandler(config_entry)

    @staticmethod
    @callback
    def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
        """Migrate old config entries."""
        version = config_entry.version
        minor = config_entry.minor_version

        _LOGGER.debug("Migrating from version %s.%s", version, minor)

        if version == 2:
            # Migrate from version 2 to 3
            new_data = {**config_entry.data}
            
            # Add new integration mode defaults
            new_data.setdefault(CONF_INTEGRATION_MODE, DEFAULT_INTEGRATION_MODE)
            new_data.setdefault(CONF_ENABLE_STACK_VIEW, DEFAULT_ENABLE_STACK_VIEW)
            new_data.setdefault(CONF_ENABLE_CONTAINER_LOGS, DEFAULT_ENABLE_CONTAINER_LOGS)
            new_data.setdefault(CONF_ENABLE_RESOURCE_SENSORS, DEFAULT_ENABLE_RESOURCE_SENSORS)
            new_data.setdefault(CONF_ENABLE_VERSION_SENSORS, DEFAULT_ENABLE_VERSION_SENSORS)
            new_data.setdefault(CONF_ENABLE_UPDATE_SENSORS, DEFAULT_ENABLE_UPDATE_SENSORS)
            new_data.setdefault(CONF_ENABLE_STACK_BUTTONS, DEFAULT_ENABLE_STACK_BUTTONS)
            new_data.setdefault(CONF_ENABLE_CONTAINER_BUTTONS, DEFAULT_ENABLE_CONTAINER_BUTTONS)
            new_data.setdefault(CONF_ENABLE_BULK_OPERATIONS, DEFAULT_ENABLE_BULK_OPERATIONS)
            
            # Update the config entry
            hass.config_entries.async_update_entry(
                config_entry,
                data=new_data,
                version=3,
                minor_version=1
            )
            _LOGGER.info("Migrated config entry from version 2 to 3")
            return True

        return True

class PortainerOptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        """Initialize options flow."""
        super().__init__()

    async def async_step_init(self, user_input=None):
        """Handle options flow."""
        if user_input is not None:
            # Validate the advanced settings
            try:
                await self._validate_advanced_config(user_input)
                return self.async_create_entry(title="", data=user_input)
            except ValueError as e:
                return self.async_show_form(
                    step_id="init",
                    data_schema=self._get_options_schema(),
                    errors={"base": "invalid_config"}
                )

        return self.async_show_form(
            step_id="init",
            data_schema=self._get_options_schema()
        )

    def _get_options_schema(self):
        """Get the options schema."""
        current_config = self.config_entry.data
        return vol.Schema({
            vol.Optional(
                CONF_INTEGRATION_MODE,
                default=current_config.get(CONF_INTEGRATION_MODE, DEFAULT_INTEGRATION_MODE),
                description="Integration mode"
            ): vol.In([INTEGRATION_MODE_LIGHTWEIGHT, INTEGRATION_MODE_STANDARD, INTEGRATION_MODE_FULL, INTEGRATION_MODE_CUSTOM]),
            
            vol.Optional(
                CONF_UPDATE_INTERVAL,
                default=current_config.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL),
                description=f"Update interval in minutes ({MIN_UPDATE_INTERVAL}-{MAX_UPDATE_INTERVAL})"
            ): vol.All(vol.Coerce(int), vol.Range(min=MIN_UPDATE_INTERVAL, max=MAX_UPDATE_INTERVAL)),
            
            vol.Optional(
                CONF_CACHE_DURATION,
                default=current_config.get(CONF_CACHE_DURATION, DEFAULT_CACHE_DURATION),
                description=f"Cache duration in hours ({MIN_CACHE_DURATION}-{MAX_CACHE_DURATION})"
            ): vol.All(vol.Coerce(int), vol.Range(min=MIN_CACHE_DURATION, max=MAX_CACHE_DURATION)),
            
            vol.Optional(
                CONF_RATE_LIMIT_CHECKS,
                default=current_config.get(CONF_RATE_LIMIT_CHECKS, DEFAULT_RATE_LIMIT_CHECKS),
                description=f"Max update checks per period ({MIN_RATE_LIMIT_CHECKS}-{MAX_RATE_LIMIT_CHECKS})"
            ): vol.All(vol.Coerce(int), vol.Range(min=MIN_RATE_LIMIT_CHECKS, max=MAX_RATE_LIMIT_CHECKS)),
            
            vol.Optional(
                CONF_RATE_LIMIT_PERIOD,
                default=current_config.get(CONF_RATE_LIMIT_PERIOD, DEFAULT_RATE_LIMIT_PERIOD),
                description="Rate limit period in hours (1-24)"
            ): vol.All(vol.Coerce(int), vol.Range(min=1, max=24)),
            
            vol.Optional(
                CONF_ENABLE_UPDATE_CHECKS,
                default=current_config.get(CONF_ENABLE_UPDATE_CHECKS, DEFAULT_ENABLE_UPDATE_CHECKS),
                description="Enable Docker image update checks"
            ): bool,
            
            vol.Optional(
                CONF_ENABLE_HEALTH_MONITORING,
                default=current_config.get(CONF_ENABLE_HEALTH_MONITORING, DEFAULT_ENABLE_HEALTH_MONITORING),
                description="Enable container health monitoring"
            ): bool,
            
            vol.Optional(
                CONF_ENABLE_RESOURCE_MONITORING,
                default=current_config.get(CONF_ENABLE_RESOURCE_MONITORING, DEFAULT_ENABLE_RESOURCE_MONITORING),
                description="Enable resource usage monitoring"
            ): bool,
            
            vol.Optional(
                CONF_ENABLE_STACK_VIEW,
                default=current_config.get(CONF_ENABLE_STACK_VIEW, DEFAULT_ENABLE_STACK_VIEW),
                description="Enable stack view and management"
            ): bool,
            
            vol.Optional(
                CONF_ENABLE_CONTAINER_LOGS,
                default=current_config.get(CONF_ENABLE_CONTAINER_LOGS, DEFAULT_ENABLE_CONTAINER_LOGS),
                description="Enable container log viewing"
            ): bool,
            
            vol.Optional(
                CONF_ENABLE_RESOURCE_SENSORS,
                default=current_config.get(CONF_ENABLE_RESOURCE_SENSORS, DEFAULT_ENABLE_RESOURCE_SENSORS),
                description="Enable CPU/memory/uptime sensors"
            ): bool,
            
            vol.Optional(
                CONF_ENABLE_VERSION_SENSORS,
                default=current_config.get(CONF_ENABLE_VERSION_SENSORS, DEFAULT_ENABLE_VERSION_SENSORS),
                description="Enable version tracking sensors"
            ): bool,
            
            vol.Optional(
                CONF_ENABLE_UPDATE_SENSORS,
                default=current_config.get(CONF_ENABLE_UPDATE_SENSORS, DEFAULT_ENABLE_UPDATE_SENSORS),
                description="Enable update availability sensors"
            ): bool,
            
            vol.Optional(
                CONF_ENABLE_STACK_BUTTONS,
                default=current_config.get(CONF_ENABLE_STACK_BUTTONS, DEFAULT_ENABLE_STACK_BUTTONS),
                description="Enable stack control buttons"
            ): bool,
            
            vol.Optional(
                CONF_ENABLE_CONTAINER_BUTTONS,
                default=current_config.get(CONF_ENABLE_CONTAINER_BUTTONS, DEFAULT_ENABLE_CONTAINER_BUTTONS),
                description="Enable container control buttons"
            ): bool,
            
            vol.Optional(
                CONF_ENABLE_BULK_OPERATIONS,
                default=current_config.get(CONF_ENABLE_BULK_OPERATIONS, DEFAULT_ENABLE_BULK_OPERATIONS),
                description="Enable bulk start/stop operations"
            ): bool,
        })

    async def _validate_advanced_config(self, config: dict) -> None:
        """Validate advanced configuration options."""
        # Validation is handled by the schema, but we can add additional checks here if needed
        pass
