"""Diagnostics support for HA Portainer Link."""

from __future__ import annotations

from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import (
    CONF_API_KEY,
    CONF_PASSWORD,
    DATA_COORDINATOR,
    DOMAIN,
)

REDACTED = "**REDACTED**"


def _redact(data: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of config data without secrets."""
    redacted = dict(data)
    for key in (CONF_API_KEY, CONF_PASSWORD):
        if key in redacted and redacted[key]:
            redacted[key] = REDACTED
    return redacted


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant,
    entry: ConfigEntry,
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    entry_data = hass.data.get(DOMAIN, {}).get(entry.entry_id, {})
    coordinator = entry_data.get(DATA_COORDINATOR)
    if coordinator is None:
        return {
            "entry": {
                "entry_id": entry.entry_id,
                "data": _redact(entry.data),
                "options": _redact(entry.options),
            },
            "loaded": False,
        }

    update_values = list(coordinator.update_availability.values())
    image_values = list(coordinator.image_data.values())
    unknown_updates = sum(
        1
        for item in image_values
        if item.get("update_reason") in {"local_digest_unknown", "remote_digest_unknown", "registry_unreachable"}
    )

    return {
        "entry": {
            "entry_id": entry.entry_id,
            "data": _redact(entry.data),
            "options": _redact(entry.options),
        },
        "loaded": True,
        "endpoint_id": coordinator.endpoint_id,
        "counts": {
            "containers": len(coordinator.containers),
            "stacks": len(coordinator.stack_names()),
            "metrics": len(coordinator.metrics),
            "image_data": len(coordinator.image_data),
            "updates_on": sum(1 for value in update_values if value),
            "updates_off": sum(1 for value in update_values if not value),
            "updates_unknown": unknown_updates,
        },
        "coordinator": {
            "last_success": coordinator.last_success.isoformat() if coordinator.last_success else None,
            "last_registry_check": (
                coordinator.last_registry_check.isoformat()
                if coordinator.last_registry_check
                else None
            ),
            "last_update_success": coordinator.last_update_success,
        },
        "api": {
            "base_url": coordinator.api.base_url,
            "ssl_verify": coordinator.api.ssl_verify,
            "last_error_class": coordinator.api.last_error_class,
        },
        "update_reasons": dict(coordinator.last_update_reasons),
    }
