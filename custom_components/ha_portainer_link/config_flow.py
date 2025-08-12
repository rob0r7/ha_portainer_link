from __future__ import annotations

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from .const import DOMAIN

class PortainerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self) -> None:
        self._user_input: dict | None = None

    async def async_step_user(self, user_input=None):
        errors = {}

        if user_input is not None:
            # Store and continue to dashboard step
            self._user_input = user_input
            return await self.async_step_dashboard()

        data_schema = vol.Schema({
            vol.Required("host"): str,
            vol.Optional("username"): str,
            vol.Optional("password"): str,
            vol.Optional("api_key"): str,
            vol.Required("endpoint_id"): int,
        })

        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    async def async_step_dashboard(self, user_input=None):
        if user_input is not None:
            create_dashboard = user_input.get("create_dashboard", True)
            dashboard_path = user_input.get("dashboard_path", "ha-portainer-link")
            dashboard_title = user_input.get("dashboard_title", "HA Portainer Link")

            data = dict(self._user_input or {})
            data.update({
                "create_dashboard": create_dashboard,
                "dashboard_path": dashboard_path,
                "dashboard_title": dashboard_title,
            })
            return self.async_create_entry(title="Portainer", data=data)

        schema = vol.Schema({
            vol.Required("create_dashboard", default=True): bool,
            vol.Optional("dashboard_title", default="HA Portainer Link"): str,
            vol.Optional("dashboard_path", default="ha-portainer-link"): str,
        })
        return self.async_show_form(step_id="dashboard", data_schema=schema)

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return PortainerOptionsFlowHandler(config_entry)

class PortainerOptionsFlowHandler(config_entries.OptionsFlow):
    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        return self.async_show_form(step_id="init", data_schema=vol.Schema({}))
