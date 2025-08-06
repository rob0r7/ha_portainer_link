import logging
from homeassistant.helpers.discovery import async_load_platform
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)
_LOGGER.warning("HA_Portainer_Link __init__.py wurde geladen")

PLATFORMS = ["sensor", "switch", "button"]

async def async_setup(hass, config):
    conf = config.get(DOMAIN)
    if conf is None:
        _LOGGER.error("No configuration found for ha_portainer_link")
        return True

    hass.data[DOMAIN] = conf

    for platform in PLATFORMS:
        _LOGGER.debug("Lade Plattform: %s", platform)
        hass.async_create_task(
            async_load_platform(hass, platform, DOMAIN, {}, config)
        )

    return True
