"""Config flow for HA Portainer Link."""

from __future__ import annotations

from urllib.parse import urlparse

import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback

from .const import (
    CONF_API_KEY,
    CONF_ENABLE_CONTAINER_BUTTONS,
    CONF_ENABLE_RESOURCE_SENSORS,
    CONF_ENABLE_STACK_BUTTONS,
    CONF_ENABLE_STACK_VIEW,
    CONF_ENABLE_UPDATE_SENSORS,
    CONF_ENABLE_VERSION_SENSORS,
    CONF_ENDPOINT_ID,
    CONF_HOST,
    CONF_NOTIFY_SERVICE,
    CONF_PASSWORD,
    CONF_UPDATE_CHECK_INTERVAL,
    CONF_UPDATE_INTERVAL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    DEFAULT_OPTIONS,
    DOMAIN,
)
from .portainer_api import PortainerAPI


class PortainerConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for HA Portainer Link."""

    VERSION = 1

    async def async_step_user(self, user_input=None):
        errors: dict[str, str] = {}

        if user_input is not None:
            normalized_host = _normalize_host(user_input[CONF_HOST])
            endpoint_id = int(user_input[CONF_ENDPOINT_ID])
            await self.async_set_unique_id(f"{normalized_host}_{endpoint_id}")
            self._abort_if_unique_id_configured()

            user_input = {**user_input, CONF_HOST: normalized_host, CONF_ENDPOINT_ID: endpoint_id}
            valid = await _validate_connection(user_input)
            if valid:
                title = f"Portainer {urlparse(normalized_host).hostname or normalized_host} ({endpoint_id})"
                return self.async_create_entry(title=title, data=user_input, options=DEFAULT_OPTIONS)
            errors["base"] = "cannot_connect"

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Optional(CONF_USERNAME): str,
                    vol.Optional(CONF_PASSWORD): str,
                    vol.Optional(CONF_API_KEY): str,
                    vol.Required(CONF_ENDPOINT_ID): int,
                    vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_OPTIONS[CONF_VERIFY_SSL]): bool,
                }
            ),
            errors=errors,
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return PortainerOptionsFlowHandler(config_entry)


class PortainerOptionsFlowHandler(config_entries.OptionsFlow):
    """Handle options for HA Portainer Link."""

    def __init__(self, config_entry):
        self.config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = {**DEFAULT_OPTIONS, **self.config_entry.options}
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_UPDATE_INTERVAL,
                        default=current[CONF_UPDATE_INTERVAL],
                    ): vol.All(vol.Coerce(int), vol.Range(min=1, max=60)),
                    vol.Required(
                        CONF_UPDATE_CHECK_INTERVAL,
                        default=current[CONF_UPDATE_CHECK_INTERVAL],
                    ): vol.All(vol.Coerce(int), vol.Range(min=60, max=86400)),
                    vol.Required(CONF_ENABLE_STACK_VIEW, default=current[CONF_ENABLE_STACK_VIEW]): bool,
                    vol.Required(
                        CONF_ENABLE_RESOURCE_SENSORS,
                        default=current[CONF_ENABLE_RESOURCE_SENSORS],
                    ): bool,
                    vol.Required(
                        CONF_ENABLE_VERSION_SENSORS,
                        default=current[CONF_ENABLE_VERSION_SENSORS],
                    ): bool,
                    vol.Required(
                        CONF_ENABLE_UPDATE_SENSORS,
                        default=current[CONF_ENABLE_UPDATE_SENSORS],
                    ): bool,
                    vol.Required(
                        CONF_ENABLE_STACK_BUTTONS,
                        default=current[CONF_ENABLE_STACK_BUTTONS],
                    ): bool,
                    vol.Required(
                        CONF_ENABLE_CONTAINER_BUTTONS,
                        default=current[CONF_ENABLE_CONTAINER_BUTTONS],
                    ): bool,
                    vol.Required(CONF_VERIFY_SSL, default=current[CONF_VERIFY_SSL]): bool,
                    vol.Optional(CONF_NOTIFY_SERVICE, default=current[CONF_NOTIFY_SERVICE]): str,
                }
            ),
        )


def _normalize_host(host: str) -> str:
    host = host.strip().rstrip("/")
    if "://" not in host:
        host = f"http://{host}"
    return host


async def _validate_connection(config: dict) -> bool:
    """Validate credentials and endpoint access without logging secrets."""
    if not config.get(CONF_API_KEY) and not (config.get(CONF_USERNAME) and config.get(CONF_PASSWORD)):
        return False

    api = PortainerAPI(
        config[CONF_HOST],
        config.get(CONF_USERNAME),
        config.get(CONF_PASSWORD),
        config.get(CONF_API_KEY),
        ssl_verify=bool(config.get(CONF_VERIFY_SSL, DEFAULT_OPTIONS[CONF_VERIFY_SSL])),
    )
    try:
        await api.initialize()
        if api.containers:
            return bool(await api.containers.check_endpoint_exists(int(config[CONF_ENDPOINT_ID])))
        containers = await api.get_containers(int(config[CONF_ENDPOINT_ID]))
        return containers is not None
    finally:
        await api.close()
