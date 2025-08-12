import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers.event import async_call_later

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "binary_sensor", "switch", "button"]

async def async_setup(hass: HomeAssistant, config: dict):
    """Set up HA Portainer Link from YAML."""

    async def _handle_create_dashboard(call: ServiceCall) -> None:
        try:
            from .dashboard import ensure_dashboard_exists
        except Exception as e:  # noqa: BLE001
            _LOGGER.warning("Dashboard helper unavailable: %s", e)
            return
        title = call.data.get("title") or "HA Protainer Link"
        url_path = call.data.get("url_path") or "ha-protainer-link"
        try:
            await ensure_dashboard_exists(hass, title=title, url_path=url_path)
            _LOGGER.info("Dashboard '%s' ensured at /%s", title, url_path)
        except Exception as e:  # noqa: BLE001
            _LOGGER.error("Failed to create dashboard: %s", e)

    hass.services.async_register(DOMAIN, "create_dashboard", _handle_create_dashboard)

    return True

async def _maybe_create_dashboard(hass: HomeAssistant, entry: ConfigEntry) -> None:
    data = entry.data or {}
    if not data.get("create_dashboard", True):
        return

    # Import lazily to avoid import errors if HA internals change
    try:
        from .dashboard import ensure_dashboard_exists
    except Exception as e:  # noqa: BLE001
        _LOGGER.debug("Dashboard helper not available: %s", e)
        return

    title: str = data.get("dashboard_title", "HA Protainer Link")
    url_path: str = data.get("dashboard_path", "ha-protainer-link")
    try:
        await ensure_dashboard_exists(hass, title=title, url_path=url_path)
        _LOGGER.info("Ensured dashboard '%s' at /%s exists", title, url_path)

        # Schedule a delayed rebuild so entities discovered after platform setup are included
        async def _delayed_rebuild(_now):
            try:
                await ensure_dashboard_exists(hass, title=title, url_path=url_path)
                _LOGGER.info("Rebuilt dashboard '%s' after initial entity load", title)
            except Exception as e:  # noqa: BLE001
                _LOGGER.debug("Delayed dashboard rebuild failed: %s", e)

        async_call_later(hass, 10, _delayed_rebuild)
    except Exception as e:  # noqa: BLE001
        _LOGGER.warning("Could not ensure dashboard exists: %s", e)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up HA Portainer Link from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = entry.data

    # ✅ Richtiger Aufruf!
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Optionally create the Lovelace dashboard
    await _maybe_create_dashboard(hass, entry)

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Unload the config entry and its platforms."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok
