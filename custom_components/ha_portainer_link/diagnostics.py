"""Diagnostics for HA Portainer Link."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import CONF_API_KEY, CONF_PASSWORD, CONF_USERNAME, DATA_COORDINATOR, DOMAIN
from .entity import container_name, container_unique_id, stable_container_key

TO_REDACT = {CONF_API_KEY, CONF_PASSWORD, CONF_USERNAME}
COMPOSE_LABELS = (
    "com.docker.compose.project",
    "com.docker.compose.service",
    "com.docker.compose.container-number",
)


async def async_get_config_entry_diagnostics(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    """Return what the integration sees, to explain missing or unavailable entities."""
    entry_data = hass.data.get(DOMAIN, {}).get(entry.entry_id) or {}
    coordinator = entry_data.get(DATA_COORDINATOR)

    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    registry_entries = er.async_entries_for_config_entry(entity_registry, entry.entry_id)
    registered_uids = {item.unique_id for item in registry_entries}

    result: dict[str, Any] = {
        "entry": {
            "data": async_redact_data(dict(entry.data), TO_REDACT),
            "options": async_redact_data(dict(entry.options), TO_REDACT),
        },
        "coordinator_loaded": coordinator is not None,
    }

    if coordinator is not None:
        last_exception = getattr(coordinator, "last_exception", None)
        result["coordinator"] = {
            "endpoint_id": coordinator.endpoint_id,
            "last_update_success": coordinator.last_update_success,
            "last_exception": repr(last_exception) if last_exception else None,
            "container_count": len(coordinator.containers),
            "portainer_stacks": [
                {"name": name, "id": stack.get("Id"), "endpoint_id": stack.get("EndpointId"), "status": stack.get("Status")}
                for name, stack in coordinator.stacks.items()
            ],
            "stack_names": coordinator.stack_names(),
        }
        containers = []
        for container_id, container in coordinator.containers.items():
            name = container_name(container)
            stack_info = coordinator.get_container_stack_info(container_id) or {}
            stable_key = stable_container_key(name, stack_info)
            status_uid = container_unique_id(entry.entry_id, coordinator.endpoint_id, stable_key, "status")
            labels = container.get("Labels") or {}
            containers.append(
                {
                    "id": container_id[:12],
                    "name": name,
                    "state": container.get("State"),
                    "status": container.get("Status"),
                    "image": container.get("Image"),
                    "compose_labels": {key: labels.get(key) for key in COMPOSE_LABELS if key in labels},
                    "stack_info": stack_info,
                    "stable_key": stable_key,
                    "status_entity_registered": status_uid in registered_uids,
                    "has_metrics": bool(coordinator.metrics.get(container_id)),
                    "has_image_data": bool(coordinator.image_data.get(container_id)),
                    "update_available": coordinator.get_update_availability(container_id),
                    "is_portainer": coordinator.is_portainer_container(container_id),
                }
            )
        result["containers"] = containers

    devices = []
    for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id):
        entities = er.async_entries_for_device(entity_registry, device.id, include_disabled_entities=True)
        devices.append(
            {
                "name": device.name,
                "identifiers": sorted(str(identifier) for identifier in device.identifiers),
                "entities": sorted(
                    f"{item.entity_id}{' (disabled)' if item.disabled_by else ''}" for item in entities
                ),
            }
        )
    result["devices"] = devices
    result["entities_without_device"] = sorted(item.entity_id for item in registry_entries if not item.device_id)
    return result
