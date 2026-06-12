"""Shared entity helpers for HA Portainer Link."""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlparse

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN


def sanitize(value: Any) -> str:
    """Return a stable identifier-safe string."""
    text = str(value or "unknown").strip().strip("/")
    text = re.sub(r"[^A-Za-z0-9_]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text.lower() or "unknown"


def host_display_name(base_url: str) -> str:
    """Return a concise display name for the Portainer host."""
    parsed = urlparse(base_url if "://" in base_url else f"http://{base_url}")
    host = parsed.hostname or base_url
    return host.split(".")[0] if not host.replace(".", "").isdigit() else host


def host_key(base_url: str) -> str:
    """Return a stable host key for identifiers."""
    parsed = urlparse(base_url if "://" in base_url else f"http://{base_url}")
    host = parsed.netloc or parsed.path or base_url
    return sanitize(host)


def container_name(container: dict[str, Any]) -> str:
    """Extract the first Docker container name."""
    names = container.get("Names") or []
    if names:
        return str(names[0]).strip("/")
    return container.get("Name", "unknown").strip("/")


def is_container_running(container: dict[str, Any] | None) -> bool:
    """Return whether a container list/inspect payload represents a running container."""
    if not container:
        return False
    state = container.get("State")
    if isinstance(state, dict):
        return bool(state.get("Running")) or state.get("Status") == "running"
    return str(state or "").lower() == "running"


def stack_info_from_container(container: dict[str, Any]) -> dict[str, Any]:
    """Extract compose stack metadata from container labels."""
    labels = container.get("Labels") or {}
    if not isinstance(labels, dict):
        labels = {}
    stack_name = labels.get("com.docker.compose.project")
    service_name = labels.get("com.docker.compose.service")
    container_number = labels.get("com.docker.compose.container-number")
    return {
        "stack_name": stack_name,
        "service_name": service_name,
        "container_number": container_number,
        "is_stack_container": bool(stack_name),
    }


def stable_container_key(container_name_value: str, stack_info: dict[str, Any]) -> str:
    """Return a stable key that survives Docker container ID changes."""
    if stack_info.get("is_stack_container"):
        parts = [
            stack_info.get("stack_name"),
            stack_info.get("service_name") or container_name_value,
            stack_info.get("container_number") or container_name_value,
        ]
        return "stack_" + "_".join(sanitize(part) for part in parts if part)
    return "container_" + sanitize(container_name_value)


def stack_key(stack_name: str) -> str:
    """Return a stable stack key."""
    return "stack_" + sanitize(stack_name)


def container_unique_id(entry_id: str, endpoint_id: int, stable_key: str, suffix: str) -> str:
    """Return a stable unique_id for a container entity."""
    return f"entry_{entry_id}_endpoint_{endpoint_id}_{sanitize(stable_key)}_{sanitize(suffix)}"


def stack_unique_id(entry_id: str, endpoint_id: int, name: str, suffix: str) -> str:
    """Return a stable unique_id for a stack entity."""
    return f"entry_{entry_id}_endpoint_{endpoint_id}_{stack_key(name)}_{sanitize(suffix)}"


def container_device_info(
    entry_id: str,
    endpoint_id: int,
    base_url: str,
    stable_key: str,
    name: str,
    container_id: str | None,
) -> dict[str, Any]:
    """Return Home Assistant device info for a standalone container."""
    host_name = host_display_name(base_url)
    device_id = f"{entry_id}_{endpoint_id}_{host_key(base_url)}_{sanitize(stable_key)}"
    return {
        "identifiers": {(DOMAIN, device_id)},
        "name": f"{name} ({host_name})",
        "manufacturer": "Docker via Portainer",
        "model": "Docker Container",
        "configuration_url": (
            f"{base_url}/#!/containers/{container_id}/details" if container_id else base_url
        ),
    }


def stack_device_info(
    entry_id: str,
    endpoint_id: int,
    base_url: str,
    name: str,
) -> dict[str, Any]:
    """Return Home Assistant device info for a Docker stack."""
    host_name = host_display_name(base_url)
    device_id = f"{entry_id}_{endpoint_id}_{host_key(base_url)}_{stack_key(name)}"
    return {
        "identifiers": {(DOMAIN, device_id)},
        "name": f"Stack: {name} ({host_name})",
        "manufacturer": "Docker via Portainer",
        "model": "Docker Stack",
        "configuration_url": f"{base_url}/#!/stacks/{name}",
    }


class BasePortainerEntity(CoordinatorEntity):
    """Base class for coordinator-backed Portainer entities."""

    _attr_should_poll = False

    def __init__(self, coordinator, entry_id: str) -> None:
        super().__init__(coordinator)
        self.entry_id = entry_id
        self.endpoint_id = coordinator.endpoint_id

    @property
    def available(self) -> bool:
        return bool(self.coordinator.last_update_success)


class BaseContainerEntity(BasePortainerEntity):
    """Base class for container-backed entities."""

    entity_suffix = "entity"

    def __init__(
        self,
        coordinator,
        entry_id: str,
        container_id: str,
        name: str,
        stack_info: dict[str, Any],
    ) -> None:
        super().__init__(coordinator, entry_id)
        self.container_id = container_id
        self.container_name = name
        self.stack_info = stack_info
        self.stable_key = stable_container_key(name, stack_info)
        self._attr_unique_id = container_unique_id(
            entry_id,
            coordinator.endpoint_id,
            self.stable_key,
            self.entity_suffix,
        )

    @property
    def current_container_id(self) -> str | None:
        current = self.coordinator.get_container_by_stable_id(self.stable_key)
        if current:
            self.container_id = current
            return current
        return self.container_id if self.container_id in self.coordinator.containers else None

    @property
    def container(self) -> dict[str, Any] | None:
        container_id = self.current_container_id
        return self.coordinator.get_container(container_id) if container_id else None

    @property
    def available(self) -> bool:
        return super().available and self.container is not None

    @property
    def device_info(self) -> dict[str, Any]:
        if self.stack_info.get("is_stack_container"):
            return stack_device_info(
                self.entry_id,
                self.endpoint_id,
                self.coordinator.api.base_url,
                self.stack_info.get("stack_name") or self.container_name,
            )
        return container_device_info(
            self.entry_id,
            self.endpoint_id,
            self.coordinator.api.base_url,
            self.stable_key,
            self.container_name,
            self.current_container_id,
        )


class BaseStackEntity(BasePortainerEntity):
    """Base class for stack-backed entities."""

    entity_suffix = "stack_entity"

    def __init__(self, coordinator, entry_id: str, stack_name_value: str) -> None:
        super().__init__(coordinator, entry_id)
        self.stack_name = stack_name_value
        self._attr_unique_id = stack_unique_id(
            entry_id,
            coordinator.endpoint_id,
            stack_name_value,
            self.entity_suffix,
        )

    @property
    def available(self) -> bool:
        return super().available and bool(self.coordinator.get_stack_containers(self.stack_name))

    @property
    def device_info(self) -> dict[str, Any]:
        return stack_device_info(
            self.entry_id,
            self.endpoint_id,
            self.coordinator.api.base_url,
            self.stack_name,
        )
