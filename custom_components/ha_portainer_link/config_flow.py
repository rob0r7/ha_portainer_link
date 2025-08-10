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
    CONF_INTEGRATION_MODE, INTEGRATION_MODE_LIGHTWEIGHT, INTEGRATION_MODE_FULL,
    INTEGRATION_MODE_PRESETS
)
from .portainer_api import PortainerAPI

_LOGGER = logging.getLogger(__name__)

class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""

class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""

class PortainerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

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
                await self._validate_connection(processed_config)
                
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
        errors = {}

        if user_input is not None:
            # Get the selected mode and its features
            selected_mode = user_input[CONF_INTEGRATION_MODE]
            mode_preset = INTEGRATION_MODE_PRESETS[selected_mode]
            
            # Apply the mode features to the configuration
            self.config_data.update(mode_preset["features"])
            self.config_data[CONF_INTEGRATION_MODE] = selected_mode
            
            # Create the entry
            return self.async_create_entry(
                title=f"Portainer ({self.config_data[CONF_HOST]}) - {selected_mode.title()}",
                data=self.config_data
            )

        # Show integration mode selection
        mode_options = {
            INTEGRATION_MODE_LIGHTWEIGHT: f"{INTEGRATION_MODE_PRESETS[INTEGRATION_MODE_LIGHTWEIGHT]['description']}",
            INTEGRATION_MODE_FULL: f"{INTEGRATION_MODE_PRESETS[INTEGRATION_MODE_FULL]['description']}"
        }

        data_schema = vol.Schema({
            vol.Required(CONF_INTEGRATION_MODE, default=INTEGRATION_MODE_FULL): vol.In(mode_options)
        })

        return self.async_show_form(
            step_id="integration_mode",
            data_schema=data_schema,
            errors=errors,
            description_placeholders={
                "lightweight_features": """
**Lightweight View Features:**
• Container start/stop switches
• Basic container status
• Less frequent updates (10 minutes)
• Minimal resource usage
                """,
                "full_features": """
**Full View Features:**
• All Lightweight features
• Stack view and management
• CPU and memory sensors
• Version tracking and updates
• Stack update buttons
• More frequent updates (5 minutes)
                """
            }
        )

    async def _process_basic_config(self, user_input: dict) -> dict:
        """Process and validate basic configuration."""
        config = user_input.copy()
        
        # Ensure host has proper scheme
        host = config[CONF_HOST].strip()
        if not host.startswith(('http://', 'https://')):
            host = f"https://{host}"
        
        config[CONF_HOST] = host
        
        # Validate endpoint ID
        if config[CONF_ENDPOINT_ID] < 1:
            raise ValueError("Endpoint ID must be at least 1")
        
        return config

    async def _validate_connection(self, config: dict) -> None:
        """Validate connection to Portainer."""
        try:
            api = PortainerAPI(
                host=config[CONF_HOST],
                username=config.get(CONF_USERNAME),
                password=config.get(CONF_PASSWORD),
                api_key=config.get(CONF_API_KEY),
                config={"endpoint_id": config[CONF_ENDPOINT_ID]}
            )
            
            # Test connection
            await api.initialize()
            
            # Test endpoint access
            containers = await api.get_containers(config[CONF_ENDPOINT_ID])
            if containers is None:
                raise CannotConnect("Could not access containers for the specified endpoint")
                
        except Exception as e:
            _LOGGER.error("Connection validation failed: %s", e)
            if "authentication" in str(e).lower() or "unauthorized" in str(e).lower():
                raise InvalidAuth("Invalid authentication credentials")
            else:
                raise CannotConnect(f"Could not connect to Portainer: {e}")

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        """Get the options flow for this handler."""
        return PortainerOptionsFlowHandler(config_entry)

    @staticmethod
    @callback
    def async_migrate_entry(hass: HomeAssistant, config_entry: ConfigEntry) -> bool:
        """Migrate old config entries to new format."""
        _LOGGER.info("Migrating config entry from version %s to 1", config_entry.version)
        
        # Migrate any version to version 1
        new_data = dict(config_entry.data)
        
        # Set default integration mode if not present
        if CONF_INTEGRATION_MODE not in new_data:
            new_data[CONF_INTEGRATION_MODE] = INTEGRATION_MODE_LIGHTWEIGHT
            # Apply lightweight mode features
            lightweight_features = INTEGRATION_MODE_PRESETS[INTEGRATION_MODE_LIGHTWEIGHT]["features"]
            new_data.update(lightweight_features)
        
        # Ensure all required features are present
        for mode_name, mode_preset in INTEGRATION_MODE_PRESETS.items():
            for feature_key, feature_value in mode_preset["features"].items():
                if feature_key not in new_data:
                    new_data[feature_key] = feature_value
        
        hass.config_entries.async_update_entry(
            config_entry,
            data=new_data,
            version=1
        )
        _LOGGER.info("Successfully migrated config entry to version 1")
        
        return True


class PortainerOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle Portainer options."""

    def __init__(self, config_entry):
        """Initialize options flow."""
        super().__init__()
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Manage the options."""
        if user_input is not None:
            # Update the integration mode
            selected_mode = user_input[CONF_INTEGRATION_MODE]
            mode_preset = INTEGRATION_MODE_PRESETS[selected_mode]
            
            # Create new config with updated mode
            new_data = dict(self.config_entry.data)
            new_data.update(mode_preset["features"])
            new_data[CONF_INTEGRATION_MODE] = selected_mode
            
            # Update the entry
            self.hass.config_entries.async_update_entry(
                self.config_entry,
                data=new_data
            )
            
            return self.async_create_entry(title="", data={})

        # Show current mode and allow changing
        current_mode = self.config_entry.data.get(CONF_INTEGRATION_MODE, INTEGRATION_MODE_LIGHTWEIGHT)
        
        mode_options = {
            INTEGRATION_MODE_LIGHTWEIGHT: f"{INTEGRATION_MODE_PRESETS[INTEGRATION_MODE_LIGHTWEIGHT]['description']}",
            INTEGRATION_MODE_FULL: f"{INTEGRATION_MODE_PRESETS[INTEGRATION_MODE_FULL]['description']}"
        }

        data_schema = vol.Schema({
            vol.Required(CONF_INTEGRATION_MODE, default=current_mode): vol.In(mode_options)
        })

        return self.async_show_form(
            step_id="init",
            data_schema=data_schema,
            description_placeholders={
                "current_mode": current_mode.title(),
                "lightweight_features": """
**Lightweight View Features:**
• Container start/stop switches
• Basic container status
• Less frequent updates (10 minutes)
• Minimal resource usage
                """,
                "full_features": """
**Full View Features:**
• All Lightweight features
• Stack view and management
• CPU and memory sensors
• Version tracking and updates
• Stack update buttons
• More frequent updates (5 minutes)
                """
            }
        )
