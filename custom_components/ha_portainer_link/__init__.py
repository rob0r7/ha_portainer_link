import logging
from datetime import timedelta
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN, CONF_SSL_VERIFY, DEFAULT_SSL_VERIFY
from .portainer_api import PortainerAPI
from .coordinator import PortainerDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "binary_sensor", "switch", "button"]

async def async_setup(hass: HomeAssistant, config: dict):
    """Set up HA Portainer Link from YAML."""
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up HA Portainer Link from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.data

    # Create API instance
    config = entry.data
    host = config["host"]
    username = config.get("username")
    password = config.get("password")
    api_key = config.get("api_key")
    endpoint_id = config["endpoint_id"]
    ssl_verify = config.get(CONF_SSL_VERIFY, DEFAULT_SSL_VERIFY)
    
    api = PortainerAPI(host, username, password, api_key, ssl_verify, config)
    
    # Initialize API
    if not await api.initialize():
        _LOGGER.error("❌ Failed to initialize Portainer API for entry %s", entry.entry_id)
        return False
    
    # Create coordinator with config
    coordinator = PortainerDataUpdateCoordinator(hass, api, endpoint_id, config)
    
    # Store coordinator for use by platforms
    hass.data[DOMAIN][f"{entry.entry_id}_coordinator"] = coordinator
    hass.data[DOMAIN][f"{entry.entry_id}_api"] = api
    hass.data[DOMAIN][f"{entry.entry_id}_endpoint_id"] = endpoint_id

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload the config entry and its platforms."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        # Clean up resources
        entry_id = entry.entry_id
        if f"{entry_id}_api" in hass.data[DOMAIN]:
            api = hass.data[DOMAIN][f"{entry_id}_api"]
            await api.close()
        
        # Remove data
        for key in [entry_id, f"{entry_id}_coordinator", f"{entry_id}_api", f"{entry_id}_endpoint_id"]:
            hass.data[DOMAIN].pop(key, None)
    
    return unload_ok
