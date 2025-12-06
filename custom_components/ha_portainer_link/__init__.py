import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.event import async_call_later

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "binary_sensor", "switch", "button"]

async def async_setup(hass: HomeAssistant, config: dict):
    """Set up HA Portainer Link from YAML."""
    # Clean up lovelace directory early for YAML setups too
    await _cleanup_lovelace_directory_early(hass)

    async def _handle_create_dashboard(call: ServiceCall) -> None:
        try:
            from .dashboard import ensure_dashboard_exists
        except Exception as e:  # noqa: BLE001
            _LOGGER.warning("Dashboard helper unavailable: %s", e)
            return
        title = call.data.get("title") or "HA Portainer Link"
        url_path = call.data.get("url_path") or "ha-portainer-link"
        try:
            await ensure_dashboard_exists(hass, title=title, url_path=url_path)
            _LOGGER.info("Dashboard '%s' ensured at /%s", title, url_path)
        except Exception as e:  # noqa: BLE001
            _LOGGER.error("Failed to create dashboard: %s", e)

    hass.services.async_register(DOMAIN, "create_dashboard", _handle_create_dashboard)

    return True

async def _maybe_create_dashboard(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Attempt to create dashboard, with retry logic to wait for Lovelace to be ready."""
    data = entry.data or {}
    if not data.get("create_dashboard", True):
        _LOGGER.info("Dashboard creation disabled in config entry")
        return

    _LOGGER.info("Starting automatic dashboard creation...")

    # Import lazily to avoid import errors if HA internals change
    try:
        from .dashboard import ensure_dashboard_exists
    except Exception as e:  # noqa: BLE001
        _LOGGER.error("Dashboard helper not available: %s", e, exc_info=True)
        return

    title: str = data.get("dashboard_title", "HA Portainer Link")
    url_path: str = data.get("dashboard_path", "ha-portainer-link")
    
    # Wait for Lovelace to be ready (with retry mechanism)
    import asyncio
    max_retries = 5
    retry_delay = 2  # seconds
    
    for attempt in range(max_retries):
        try:
            # Check if Lovelace is available
            ll_data = hass.data.get("lovelace")
            if ll_data is None and attempt < max_retries - 1:
                _LOGGER.debug("Lovelace not ready yet, waiting... (attempt %d/%d)", attempt + 1, max_retries)
                await asyncio.sleep(retry_delay)
                continue
            
            await ensure_dashboard_exists(hass, title=title, url_path=url_path)
            _LOGGER.info("✅ Successfully ensured dashboard '%s' at /%s exists", title, url_path)

            # Schedule a delayed rebuild so entities discovered after platform setup are included
            async def _delayed_rebuild(_now):
                try:
                    await ensure_dashboard_exists(hass, title=title, url_path=url_path)
                    _LOGGER.info("Rebuilt dashboard '%s' after initial entity load", title)
                except Exception as e:  # noqa: BLE001
                    _LOGGER.error("Delayed dashboard rebuild failed: %s", e, exc_info=True)

            async_call_later(hass, 10, _delayed_rebuild)
            return  # Success, exit function
        except Exception as e:  # noqa: BLE001
            if attempt < max_retries - 1:
                _LOGGER.warning("Dashboard creation failed, retrying... (attempt %d/%d): %s", attempt + 1, max_retries, e)
                await asyncio.sleep(retry_delay)
            else:
                _LOGGER.error("Could not ensure dashboard exists after %d attempts: %s", max_retries, e, exc_info=True)

async def _cleanup_lovelace_directory_early(hass: HomeAssistant) -> None:
    """Clean up incorrectly created lovelace directory as early as possible.
    
    NOTE: This may run too late if Home Assistant has already tried to read the file.
    If you see errors about lovelace being a directory, manually remove it:
    rm -rf /config/.storage/lovelace
    """
    try:
        from pathlib import Path
        
        config_dir = Path(hass.config.config_dir)
        storage_dir = config_dir / ".storage"
        lovelace_path = storage_dir / "lovelace"
        
        def _remove_directory():
            if lovelace_path.exists() and lovelace_path.is_dir():
                _LOGGER.warning(
                    "⚠️ Found incorrectly created lovelace directory! "
                    "Home Assistant expects /config/.storage/lovelace to be a JSON file, not a directory. "
                    "Attempting to remove it..."
                )
                import shutil
                try:
                    shutil.rmtree(lovelace_path)
                    _LOGGER.info("✅ Successfully removed lovelace directory. Home Assistant restart recommended.")
                    return True
                except Exception as e:
                    _LOGGER.error(
                        "❌ Failed to remove lovelace directory automatically: %s\n"
                        "Please manually remove it: rm -rf %s",
                        e, lovelace_path
                    )
                    return False
            return True
        
        await hass.async_add_executor_job(_remove_directory)
    except Exception as e:
        _LOGGER.debug("Early lovelace cleanup check failed: %s", e)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up HA Portainer Link from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.data

    # Clean up lovelace directory IMMEDIATELY before anything else
    await _cleanup_lovelace_directory_early(hass)

    # Start dashboard creation concurrently so it's not blocked by platform setup
    hass.async_create_task(_maybe_create_dashboard(hass, entry))

    # ✅ Richtiger Aufruf!
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload the config entry and its platforms."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
