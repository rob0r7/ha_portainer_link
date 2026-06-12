"""HA Portainer Link integration setup."""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import (
    CONF_API_KEY,
    CONF_ENDPOINT_ID,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    DATA_API,
    DATA_COORDINATOR,
    DEFAULT_OPTIONS,
    DOMAIN,
)
from .coordinator import PortainerDataUpdateCoordinator
from .entity import container_name, container_unique_id, stable_container_key, sanitize
from .portainer_api import PortainerAPI

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "binary_sensor", "switch", "button", "update"]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up HA Portainer Link services."""
    hass.data.setdefault(DOMAIN, {})
    _register_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up HA Portainer Link from a config entry."""
    hass.data.setdefault(DOMAIN, {})
    config = {**DEFAULT_OPTIONS, **entry.data, **entry.options}
    api = PortainerAPI(
        config[CONF_HOST],
        config.get(CONF_USERNAME),
        config.get(CONF_PASSWORD),
        config.get(CONF_API_KEY),
        ssl_verify=bool(config.get(CONF_VERIFY_SSL, DEFAULT_OPTIONS[CONF_VERIFY_SSL])),
    )

    try:
        await api.initialize()
        coordinator = PortainerDataUpdateCoordinator(
            hass,
            api,
            int(config[CONF_ENDPOINT_ID]),
            config,
        )
        await coordinator.async_config_entry_first_refresh()
    except Exception:
        await api.close()
        raise

    hass.data[DOMAIN][entry.entry_id] = {
        DATA_API: api,
        DATA_COORDINATOR: coordinator,
    }
    _migrate_entity_unique_ids(hass, entry, coordinator)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    _register_services(hass)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _cleanup_empty_devices(hass, entry)
    return True


async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Reload entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload config entry platforms and close resources."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    data = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
    if data:
        coordinator = data.get(DATA_COORDINATOR)
        if coordinator:
            await coordinator.async_shutdown()
        elif data.get(DATA_API):
            await data[DATA_API].close()
    has_entries = any(
        key != "_services_registered" and isinstance(value, dict)
        for key, value in hass.data.get(DOMAIN, {}).items()
    )
    if unload_ok and not has_entries:
        _unregister_services(hass)
    return unload_ok


def _register_services(hass: HomeAssistant) -> None:
    """Register integration services once."""
    registered = hass.data[DOMAIN].setdefault("_services_registered", False)
    if registered:
        return

    async def handle_reload(call: ServiceCall) -> None:
        for entry in hass.config_entries.async_entries(DOMAIN):
            await hass.config_entries.async_reload(entry.entry_id)

    async def handle_refresh(call: ServiceCall) -> None:
        for entry_data in list(hass.data.get(DOMAIN, {}).values()):
            if isinstance(entry_data, dict) and (coordinator := entry_data.get(DATA_COORDINATOR)):
                await coordinator.async_request_refresh()

    hass.services.async_register(DOMAIN, "reload", handle_reload)
    hass.services.async_register(DOMAIN, "refresh", handle_refresh)
    hass.data[DOMAIN]["_services_registered"] = True


def _unregister_services(hass: HomeAssistant) -> None:
    """Unregister integration services."""
    for service in ("reload", "refresh"):
        if hass.services.has_service(DOMAIN, service):
            hass.services.async_remove(DOMAIN, service)
    hass.data.setdefault(DOMAIN, {})["_services_registered"] = False


def _cleanup_empty_devices(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Remove stale devices for this entry that no longer have entities."""
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id):
        entities = er.async_entries_for_device(entity_registry, device.id)
        if not entities:
            device_registry.async_remove_device(device.id)


def _migrate_entity_unique_ids(
    hass: HomeAssistant,
    entry: ConfigEntry,
    coordinator: PortainerDataUpdateCoordinator,
) -> None:
    """Migrate old container-id-based unique IDs to stable keys."""
    registry = er.async_get(hass)
    suffix_domains = {
        "status": "sensor",
        "cpu_usage": "sensor",
        "memory_usage": "sensor",
        "uptime": "sensor",
        "image": "sensor",
        "current_version": "sensor",
        "available_version": "sensor",
        "current_digest": "sensor",
        "available_digest": "sensor",
        "update_available": "binary_sensor",
        "switch": "switch",
        "restart": "button",
        "pull_update": "button",
        "update": "update",
    }
    for container_id, container in coordinator.containers.items():
        name = container_name(container)
        stack_info = coordinator.get_container_stack_info(container_id) or {}
        stable_key = stable_container_key(name, stack_info)
        old_stack_key = None
        if stack_info.get("is_stack_container"):
            old_stack_key = sanitize(
                f"{stack_info.get('stack_name')}_{stack_info.get('service_name') or name}"
            )
        for suffix, domain in suffix_domains.items():
            new_uid = container_unique_id(entry.entry_id, coordinator.endpoint_id, stable_key, suffix)
            old_uids = [
                f"entry_{entry.entry_id}_endpoint_{coordinator.endpoint_id}_{container_id}_{suffix}",
            ]
            if old_stack_key:
                old_uids.append(
                    f"entry_{entry.entry_id}_endpoint_{coordinator.endpoint_id}_{old_stack_key}_{suffix}"
                )
            for old_uid in old_uids:
                entity_id = registry.async_get_entity_id(domain, DOMAIN, old_uid)
                if entity_id and old_uid != new_uid and not registry.async_get_entity_id(domain, DOMAIN, new_uid):
                    registry.async_update_entity(entity_id, new_unique_id=new_uid)
