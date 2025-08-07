import logging
import asyncio
from datetime import timedelta
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.helpers.event import async_track_time_interval

from .const import DOMAIN
from .portainer_api import PortainerAPI

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
    
    api = PortainerAPI(host, username, password, api_key)
    await api.initialize()
    
    # Store API instance for use by platforms
    hass.data[DOMAIN][f"{entry.entry_id}_api"] = api
    hass.data[DOMAIN][f"{entry.entry_id}_endpoint_id"] = endpoint_id

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Start container ID update mechanism
    async def update_container_ids(now=None):
        """Periodically check for container ID changes and update entities."""
        try:
            containers = await api.get_containers(endpoint_id)
            container_map = {}
            
            # Create a map of container name -> container ID
            for container in containers:
                name = container.get("Names", ["unknown"])[0].strip("/")
                container_id = container["Id"]
                container_map[name] = container_id
            
            # Update entities with new container IDs
            for platform in PLATFORMS:
                entities = hass.data.get(f"{entry.entry_id}_{platform}", [])
                for entity in entities:
                    if hasattr(entity, 'update_container_id') and hasattr(entity, '_container_name'):
                        current_id = entity._container_id
                        new_id = container_map.get(entity._container_name)
                        if new_id and new_id != current_id:
                            entity.update_container_id(new_id)
                            _LOGGER.info("🔄 Updated container ID for %s: %s -> %s", 
                                        entity._container_name, current_id[:12], new_id[:12])
            
        except Exception as e:
            _LOGGER.warning("Failed to update container IDs: %s", e)

    # Run container ID updates every 30 seconds
    async_track_time_interval(hass, update_container_ids, timedelta(seconds=30))

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload the config entry and its platforms."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
