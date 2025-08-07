import logging
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .portainer_api import PortainerAPI

_LOGGER = logging.getLogger(__name__)

class CannotConnect(HomeAssistantError):
    """Error to indicate we cannot connect."""

class InvalidAuth(HomeAssistantError):
    """Error to indicate there is invalid auth."""

class PortainerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    async def async_step_user(self, user_input=None) -> FlowResult:
        """Handle the initial step."""
        errors = {}

        if user_input is not None:
            try:
                # Validate the configuration
                await self._validate_config(user_input)
                
                # Create the entry
                return self.async_create_entry(
                    title=f"Portainer ({user_input['host']})", 
                    data=user_input
                )
            except CannotConnect:
                errors["base"] = "cannot_connect"
            except InvalidAuth:
                errors["base"] = "invalid_auth"
            except Exception:  # pylint: disable=broad-except
                _LOGGER.exception("Unexpected exception")
                errors["base"] = "unknown"

        data_schema = vol.Schema({
            vol.Required("host", description="Portainer host URL"): str,
            vol.Optional("username", description="Username"): str,
            vol.Optional("password", description="Password"): str,
            vol.Optional("api_key", description="API Key"): str,
            vol.Required("endpoint_id", description="Docker endpoint ID (usually 1)"): int,
        })

        return self.async_show_form(
            step_id="user", 
            data_schema=data_schema, 
            errors=errors
        )

    async def _validate_config(self, config: dict) -> None:
        """Validate the configuration."""
        host = config["host"]
        username = config.get("username")
        password = config.get("password")
        api_key = config.get("api_key")
        endpoint_id = config["endpoint_id"]

        # Validate host URL
        if not host.startswith(("http://", "https://")):
            raise ValueError("Host must start with http:// or https://")

        # Validate authentication
        if not api_key and (not username or not password):
            raise InvalidAuth("Either API key or username/password must be provided")

        # Validate endpoint ID
        if not isinstance(endpoint_id, int) or endpoint_id < 1:
            raise ValueError("Endpoint ID must be a positive integer")

        # Test connection
        try:
            api = PortainerAPI(host, username, password, api_key)
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

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return PortainerOptionsFlowHandler(config_entry)

class PortainerOptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        """Handle options flow."""
        return self.async_show_form(step_id="init", data_schema=vol.Schema({}))
