import logging
from datetime import timedelta
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import service
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity_registry import RegistryEntry

from .const import DOMAIN, INTEGRATION_MODE_PRESETS
from .portainer_api import PortainerAPI
from .coordinator import PortainerDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

# Define platforms here since it's used in this file
PLATFORMS = ["sensor", "binary_sensor", "switch", "button"]

def create_portainer_device_info(entry_id: str, host: str, name: str = None) -> DeviceInfo:
    """Create device info for Portainer endpoint."""
    return DeviceInfo(
        entry_type=DeviceEntryType.SERVICE,
        identifiers={(DOMAIN, entry_id)},
        name=name or f"Portainer ({host})",
        manufacturer="Portainer",
        model="Portainer CE",
        configuration_url=host,
    )

def create_stack_device_info(entry_id: str, stack_id: str, stack_name: str) -> DeviceInfo:
    """Create device info for a Docker stack."""
    return DeviceInfo(
        entry_type=DeviceEntryType.SERVICE,
        identifiers={(DOMAIN, entry_id, "stack", stack_id)},
        name=f"Stack: {stack_name}",
        manufacturer="Docker",
        model="Docker Stack",
    )

def create_container_device_info(entry_id: str, container_id: str, container_name: str, stack_info: dict = None) -> DeviceInfo:
    """Create device info for a Docker container."""
    # Determine the parent device
    if stack_info and stack_info.get("is_stack_container"):
        # Container belongs to a stack
        stack_id = stack_info.get("stack_id")
        stack_name = stack_info.get("stack_name", "unknown")
        name = f"Container: {container_name}"
    else:
        # Standalone container
        name = f"Container: {container_name}"
    
    return DeviceInfo(
        entry_type=DeviceEntryType.SERVICE,
        identifiers={(DOMAIN, entry_id, "container", container_id)},
        name=name,
        manufacturer="Docker",
        model="Docker Container",
    )

async def async_setup(hass: HomeAssistant, config: dict):
    """Set up HA Portainer Link from YAML."""
    
    async def reload_portainer_integration(call: ServiceCall):
        """Reload all Portainer integrations."""
        _LOGGER.info("🔄 Reloading all Portainer integrations via service call")
        
        # Get all config entries for this domain
        entries = hass.config_entries.async_entries(DOMAIN)
        
        for entry in entries:
            try:
                await async_reload_entry(hass, entry)
                _LOGGER.info("✅ Successfully reloaded entry: %s", entry.title)
            except Exception as e:
                _LOGGER.error("❌ Failed to reload entry %s: %s", entry.title, e)
    
    async def refresh_container_data(call: ServiceCall):
        """Force refresh container data for all Portainer integrations."""
        _LOGGER.info("🔄 Force refreshing container data for all Portainer integrations")
        
        # Get all config entries for this domain
        entries = hass.config_entries.async_entries(DOMAIN)
        
        for entry in entries:
            try:
                entry_id = entry.entry_id
                if f"{entry_id}_coordinator" in hass.data.get(DOMAIN, {}):
                    coordinator = hass.data[DOMAIN][f"{entry_id}_coordinator"]
                    await coordinator.async_request_refresh()
                    _LOGGER.info("✅ Force refreshed data for entry: %s", entry.title)
                else:
                    _LOGGER.warning("⚠️ No coordinator found for entry: %s", entry.title)
            except Exception as e:
                _LOGGER.error("❌ Failed to refresh entry %s: %s", entry.title, e)
    
    # Register the reload service
    hass.services.async_register(DOMAIN, "reload", reload_portainer_integration)
    
    # Register the refresh service
    hass.services.async_register(DOMAIN, "refresh", refresh_container_data)
    
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up HA Portainer Link from a config entry."""
    config = dict(entry.data)  # Create mutable copy
    endpoint_id = config["endpoint_id"]
    entry_id = entry.entry_id

    _LOGGER.info("🚀 Setting up HA Portainer Link for entry %s (endpoint %s)", entry_id, endpoint_id)
    
    # Apply integration mode presets
    integration_mode = config.get("integration_mode", "lightweight")
    if integration_mode in INTEGRATION_MODE_PRESETS:
        preset_features = INTEGRATION_MODE_PRESETS[integration_mode]["features"]
        config.update(preset_features)
        _LOGGER.info("📊 Applied %s mode features: %s", integration_mode, list(preset_features.keys()))
    
    # Create API instance
    api = PortainerAPI(
        host=config["host"],
        username=config.get("username"),  # Optional
        password=config.get("password"),  # Optional
        api_key=config.get("api_key"),   # Optional
        config=config
    )
    
    # Initialize API
    if not await api.initialize():
        _LOGGER.error("❌ Failed to initialize Portainer API")
        return False
    
    # Create coordinator
    coordinator = PortainerDataUpdateCoordinator(hass, api, endpoint_id, config)
    
    # Initialize DOMAIN in hass.data if it doesn't exist
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}
    
    # Store coordinator in hass data
    hass.data[DOMAIN][f"{entry_id}_coordinator"] = coordinator
    
    # Initialize coordinator data (only once)
    try:
        await coordinator.async_config_entry_first_refresh()
        _LOGGER.info("✅ Coordinator initialized successfully")
    except Exception as e:
        _LOGGER.error("❌ Failed to initialize coordinator: %s", e)
        return False
    
    # Forward the setup to the platforms
    hass.async_create_task(
        hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    )
    
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload the config entry and its platforms."""
    entry_id = entry.entry_id
    _LOGGER.info("🔄 Unloading Portainer integration for entry: %s", entry_id)
    
    # Stop coordinator first
    if f"{entry_id}_coordinator" in hass.data.get(DOMAIN, {}):
        coordinator = hass.data[DOMAIN][f"{entry_id}_coordinator"]
        if hasattr(coordinator, 'async_shutdown'):
            await coordinator.async_shutdown()
        _LOGGER.debug("🛑 Stopped coordinator for entry %s", entry_id)
    
    # Unload platforms
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    
    if unload_ok:
        # Clean up API resources
        if f"{entry_id}_api" in hass.data.get(DOMAIN, {}):
            api = hass.data[DOMAIN][f"{entry_id}_api"]
            try:
                await api.close()
                _LOGGER.debug("🔌 Closed API session for entry %s", entry_id)
            except Exception as e:
                _LOGGER.warning("⚠️ Error closing API session: %s", e)
        
        # Remove all data for this entry
        if DOMAIN in hass.data:
            keys_to_remove = [entry_id, f"{entry_id}_coordinator", f"{entry_id}_api", f"{entry_id}_endpoint_id"]
            for key in keys_to_remove:
                if key in hass.data[DOMAIN]:
                    _LOGGER.debug("🧹 Removing data key: %s", key)
                    hass.data[DOMAIN].pop(key, None)
            
            # If no more entries, clean up the entire domain
            if not any(key for key in hass.data[DOMAIN].keys() if not key.endswith('_coordinator') and not key.endswith('_api') and not key.endswith('_endpoint_id')):
                _LOGGER.debug("🧹 Cleaning up entire domain data")
                hass.data.pop(DOMAIN, None)
    
    _LOGGER.info("✅ Unload %s for entry %s", "successful" if unload_ok else "failed", entry_id)
    return unload_ok

async def async_reload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Reload the config entry."""
    _LOGGER.info("🔄 Reloading Portainer integration for entry: %s", entry.entry_id)
    
    # Unload first
    await async_unload_entry(hass, entry)
    
    # Wait a moment for cleanup
    import asyncio
    await asyncio.sleep(1)
    
    # Set up again
    return await async_setup_entry(hass, entry)
