import logging
_LOGGER = logging.getLogger(__name__)
_LOGGER.warning("HA_Portainer_Link __init__.py wurde geladen")
from homeassistant.helpers.discovery import async_load_platform

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass, config):
    """Set up ha_portainer_link integration from configuration.yaml."""
    conf = config.get(DOMAIN)
    if conf is None:
        _LOGGER.error("No configuration found for ha_portainer_link")
        return True

    hass.data[DOMAIN] = conf

    hass.async_create_task(
        async_load_platform(hass, "sensor", DOMAIN, {}, config)
    )
    hass.async_create_task(
        async_load_platform(hass, "switch", DOMAIN, {}, config)
    )

    return True
