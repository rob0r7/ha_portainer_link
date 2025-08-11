from __future__ import annotations
import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from typing import Any, Dict
from .const import DOMAIN

INTEGRATION_MODES = ["Lightweight", "Full", "Custom"]

# Defaults per mode
MODE_DEFAULTS = {
    "Lightweight": {
        "enable_stack_view": False,
        "enable_resource_sensors": False,
        "enable_version_sensors": False,
        "enable_update_sensors": False,
        "enable_stack_buttons": False,
        "enable_container_buttons": True,
        "update_interval": 10,
    },
    "Full": {
        "enable_stack_view": True,
        "enable_resource_sensors": True,
        "enable_version_sensors": True,
        "enable_update_sensors": True,
        "enable_stack_buttons": True,
        "enable_container_buttons": True,
        "update_interval": 5,
    },
}


def _merge_options(data: Dict[str, Any], options: Dict[str, Any] | None) -> Dict[str, Any]:
    merged = dict(data)
    if options:
        merged.update(options)
    return merged


class PortainerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._base_data: Dict[str, Any] | None = None

    async def async_step_user(self, user_input: Dict[str, Any] | None = None):
        errors: Dict[str, str] = {}

        if user_input is not None:
            mode = user_input.pop("integration_mode", "Full")
            base_data = user_input

            if mode == "Custom":
                self._base_data = base_data
                return await self.async_step_features()

            # Apply mode defaults and create entry
            defaults = MODE_DEFAULTS.get(mode, MODE_DEFAULTS["Full"])  # fallback to Full
            entry_data = {**base_data, **defaults, "integration_mode": mode}
            return self.async_create_entry(title="Portainer", data=entry_data)

        data_schema = vol.Schema(
            {
                vol.Required("host"): str,
                vol.Optional("username"): str,
                vol.Optional("password"): str,
                vol.Optional("api_key"): str,
                vol.Required("endpoint_id"): int,
                vol.Required("integration_mode", default="Full"): vol.In(INTEGRATION_MODES),
            }
        )

        return self.async_show_form(step_id="user", data_schema=data_schema, errors=errors)

    async def async_step_features(self, user_input: Dict[str, Any] | None = None):
        """Second step for Custom mode: expose feature toggles."""
        assert self._base_data is not None
        if user_input is not None:
            entry_data = {
                **self._base_data,
                **user_input,
                "integration_mode": "Custom",
            }
            return self.async_create_entry(title="Portainer", data=entry_data)

        # Reasonable defaults for Custom if not provided yet
        defaults = MODE_DEFAULTS["Full"]
        data_schema = vol.Schema(
            {
                vol.Required("enable_stack_view", default=defaults["enable_stack_view"]): bool,
                vol.Required("enable_resource_sensors", default=defaults["enable_resource_sensors"]): bool,
                vol.Required("enable_version_sensors", default=defaults["enable_version_sensors"]): bool,
                vol.Required("enable_update_sensors", default=defaults["enable_update_sensors"]): bool,
                vol.Required("enable_stack_buttons", default=defaults["enable_stack_buttons"]): bool,
                vol.Required("enable_container_buttons", default=defaults["enable_container_buttons"]): bool,
                vol.Required("update_interval", default=defaults["update_interval"]): int,
            }
        )
        return self.async_show_form(step_id="features", data_schema=data_schema)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return PortainerOptionsFlowHandler(config_entry)


class PortainerOptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry: config_entries.ConfigEntry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input: Dict[str, Any] | None = None):
        data = self.config_entry.data
        options = self.config_entry.options
        current = _merge_options(data, options)

        if user_input is not None:
            # Persist only options (do not overwrite data)
            return self.async_create_entry(title="", data=user_input)

        # Build options form using current values as defaults
        schema = vol.Schema(
            {
                vol.Required("enable_stack_view", default=current.get("enable_stack_view", False)): bool,
                vol.Required("enable_resource_sensors", default=current.get("enable_resource_sensors", False)): bool,
                vol.Required("enable_version_sensors", default=current.get("enable_version_sensors", False)): bool,
                vol.Required("enable_update_sensors", default=current.get("enable_update_sensors", False)): bool,
                vol.Required("enable_stack_buttons", default=current.get("enable_stack_buttons", False)): bool,
                vol.Required("enable_container_buttons", default=current.get("enable_container_buttons", True)): bool,
                vol.Required("update_interval", default=current.get("update_interval", 5)): int,
            }
        )

        return self.async_show_form(step_id="init", data_schema=schema)
