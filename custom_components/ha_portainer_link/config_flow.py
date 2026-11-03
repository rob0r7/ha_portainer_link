"""Config flow for HA Portainer Link."""

from __future__ import annotations

import logging
from urllib.parse import urlparse

import voluptuous as vol
from aiohttp.client_exceptions import ClientConnectorCertificateError
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
)

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
    SSL_VERIFY_FAILED_MESSAGE,
)
from .portainer_api import PortainerAPI, PortainerAuthError

_LOGGER = logging.getLogger(__name__)

TEXT = TextSelector()
PASSWORD = TextSelector(TextSelectorConfig(type=TextSelectorType.PASSWORD))
BOOLEAN = BooleanSelector()
ENDPOINT_ID = NumberSelector(NumberSelectorConfig(min=1, step=1, mode=NumberSelectorMode.BOX))
UPDATE_INTERVAL = NumberSelector(
    NumberSelectorConfig(min=1, max=60, step=1, unit_of_measurement="min", mode=NumberSelectorMode.BOX)
)
UPDATE_CHECK_INTERVAL = NumberSelector(
    NumberSelectorConfig(min=60, max=43200, step=30, unit_of_measurement="min", mode=NumberSelectorMode.BOX)
)


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
            error = await _validate_connection(user_input)
            if error is None:
                title = f"Portainer {urlparse(normalized_host).hostname or normalized_host} ({endpoint_id})"
                return self.async_create_entry(title=title, data=user_input, options=DEFAULT_OPTIONS)
            errors["base"] = error

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): TEXT,
                    vol.Optional(CONF_API_KEY): PASSWORD,
                    vol.Optional(CONF_USERNAME): TEXT,
                    vol.Optional(CONF_PASSWORD): PASSWORD,
                    vol.Required(CONF_ENDPOINT_ID, default=1): ENDPOINT_ID,
                    vol.Optional(CONF_VERIFY_SSL, default=DEFAULT_OPTIONS[CONF_VERIFY_SSL]): BOOLEAN,
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
        self._config_entry = config_entry

    async def async_step_init(self, user_input=None):
        if user_input is not None:
            options = {**user_input}
            # Number selectors return floats; the rest of the integration expects whole minutes.
            options[CONF_UPDATE_INTERVAL] = int(options[CONF_UPDATE_INTERVAL])
            options[CONF_UPDATE_CHECK_INTERVAL] = int(options[CONF_UPDATE_CHECK_INTERVAL])
            # An emptied optional field is omitted; store "" so persistent notifications are used.
            options[CONF_NOTIFY_SERVICE] = (options.get(CONF_NOTIFY_SERVICE) or "").strip()
            return self.async_create_entry(title="", data=options)

        current = {**DEFAULT_OPTIONS, **self._config_entry.options}
        notify_services = sorted(f"notify.{name}" for name in self.hass.services.async_services().get("notify", {}))
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_UPDATE_INTERVAL, default=current[CONF_UPDATE_INTERVAL]): UPDATE_INTERVAL,
                    vol.Required(
                        CONF_UPDATE_CHECK_INTERVAL,
                        default=current[CONF_UPDATE_CHECK_INTERVAL],
                    ): UPDATE_CHECK_INTERVAL,
                    vol.Required(CONF_ENABLE_STACK_VIEW, default=current[CONF_ENABLE_STACK_VIEW]): BOOLEAN,
                    vol.Required(CONF_ENABLE_STACK_BUTTONS, default=current[CONF_ENABLE_STACK_BUTTONS]): BOOLEAN,
                    vol.Required(
                        CONF_ENABLE_CONTAINER_BUTTONS,
                        default=current[CONF_ENABLE_CONTAINER_BUTTONS],
                    ): BOOLEAN,
                    vol.Required(
                        CONF_ENABLE_RESOURCE_SENSORS,
                        default=current[CONF_ENABLE_RESOURCE_SENSORS],
                    ): BOOLEAN,
                    vol.Required(
                        CONF_ENABLE_VERSION_SENSORS,
                        default=current[CONF_ENABLE_VERSION_SENSORS],
                    ): BOOLEAN,
                    vol.Required(
                        CONF_ENABLE_UPDATE_SENSORS,
                        default=current[CONF_ENABLE_UPDATE_SENSORS],
                    ): BOOLEAN,
                    vol.Required(CONF_VERIFY_SSL, default=current[CONF_VERIFY_SSL]): BOOLEAN,
                    vol.Optional(
                        CONF_NOTIFY_SERVICE,
                        description={"suggested_value": current[CONF_NOTIFY_SERVICE] or None},
                    ): SelectSelector(
                        SelectSelectorConfig(
                            options=notify_services,
                            custom_value=True,
                            mode=SelectSelectorMode.DROPDOWN,
                        )
                    ),
                }
            ),
        )


def _normalize_host(host: str) -> str:
    host = host.strip().rstrip("/")
    if "://" not in host:
        host = f"http://{host}"
    return host


async def _validate_connection(config: dict) -> str | None:
    """Validate credentials and endpoint access without logging secrets.

    Returns None on success, otherwise a config flow error key.
    """
    if not config.get(CONF_API_KEY) and not (config.get(CONF_USERNAME) and config.get(CONF_PASSWORD)):
        return "invalid_auth"

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
            exists = await api.containers.check_endpoint_exists(int(config[CONF_ENDPOINT_ID]))
        else:
            exists = await api.get_containers(int(config[CONF_ENDPOINT_ID])) is not None
        return None if exists else "cannot_connect"
    except ClientConnectorCertificateError:
        _LOGGER.warning(SSL_VERIFY_FAILED_MESSAGE)
        return "ssl_error"
    except PortainerAuthError as err:
        _LOGGER.warning("%s", err)
        return "invalid_auth"
    except Exception as err:
        _LOGGER.warning("Cannot connect to Portainer: %s", err)
        return "cannot_connect"
    finally:
        await api.close()
