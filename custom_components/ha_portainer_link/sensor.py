"""Sensor platform for HA Portainer Link."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import SensorEntity

from .const import DATA_COORDINATOR, DOMAIN
from .entity import BaseContainerEntity, container_name, is_container_running


async def async_setup_entry(hass, entry, async_add_entities) -> None:
    """Set up Portainer sensors."""
    coordinator = hass.data[DOMAIN][entry.entry_id][DATA_COORDINATOR]
    entities: list[SensorEntity] = []

    for container_id, container in coordinator.containers.items():
        name = container_name(container)
        stack_info = coordinator.get_container_stack_info(container_id) or {}
        entities.append(ContainerStatusSensor(coordinator, entry.entry_id, container_id, name, stack_info))
        entities.append(ContainerImageSensor(coordinator, entry.entry_id, container_id, name, stack_info))
        if coordinator.is_resource_sensors_enabled():
            entities.extend(
                [
                    ContainerCPUSensor(coordinator, entry.entry_id, container_id, name, stack_info),
                    ContainerMemorySensor(coordinator, entry.entry_id, container_id, name, stack_info),
                    ContainerUptimeSensor(coordinator, entry.entry_id, container_id, name, stack_info),
                ]
            )
        if coordinator.is_version_sensors_enabled():
            entities.extend(
                [
                    ContainerCurrentVersionSensor(coordinator, entry.entry_id, container_id, name, stack_info),
                    ContainerAvailableVersionSensor(coordinator, entry.entry_id, container_id, name, stack_info),
                    ContainerCurrentDigestSensor(coordinator, entry.entry_id, container_id, name, stack_info),
                    ContainerAvailableDigestSensor(coordinator, entry.entry_id, container_id, name, stack_info),
                ]
            )

    async_add_entities(entities)


class PortainerContainerSensor(BaseContainerEntity, SensorEntity):
    """Base class for container sensors."""

    icon_name = "mdi:docker"

    def __init__(self, coordinator, entry_id: str, container_id: str, name: str, stack_info: dict[str, Any]) -> None:
        super().__init__(coordinator, entry_id, container_id, name, stack_info)
        self._attr_name = f"{name} {self.label}"
        self._attr_icon = self.icon_name

    @property
    def native_value(self):
        return None

    def metric(self, key: str):
        container_id = self.current_container_id
        return self.coordinator.metrics.get(container_id or "", {}).get(key)

    def image_value(self, key: str):
        container_id = self.current_container_id
        return self.coordinator.image_data.get(container_id or "", {}).get(key)


class ContainerStatusSensor(PortainerContainerSensor):
    entity_suffix = "status"
    label = "Status"

    @property
    def native_value(self):
        container = self.container
        if not container:
            return None
        state = container.get("State")
        if isinstance(state, dict):
            return state.get("Status") or ("running" if state.get("Running") else "stopped")
        return state or "unknown"


class ContainerCPUSensor(PortainerContainerSensor):
    entity_suffix = "cpu_usage"
    label = "CPU Usage"
    icon_name = "mdi:cpu-64-bit"
    _attr_native_unit_of_measurement = "%"

    @property
    def native_value(self):
        return self.metric("cpu_percent")


class ContainerMemorySensor(PortainerContainerSensor):
    entity_suffix = "memory_usage"
    label = "Memory Usage"
    icon_name = "mdi:memory"
    _attr_native_unit_of_measurement = "MB"

    @property
    def native_value(self):
        return self.metric("memory_mb")


class ContainerUptimeSensor(PortainerContainerSensor):
    entity_suffix = "uptime"
    label = "Uptime"
    icon_name = "mdi:clock-outline"

    @property
    def native_value(self):
        if not is_container_running(self.container):
            return "Not running"
        uptime_s = self.metric("uptime_s")
        if uptime_s is None:
            return None
        days, remainder = divmod(int(uptime_s), 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, _ = divmod(remainder, 60)
        if days:
            return f"{days}d {hours}h"
        if hours:
            return f"{hours}h {minutes}m"
        return f"{minutes}m"


class ContainerImageSensor(PortainerContainerSensor):
    entity_suffix = "image"
    label = "Image"
    icon_name = "mdi:docker"

    @property
    def native_value(self):
        container = self.container
        if not container:
            return None
        return self.image_value("image_name") or container.get("Image")


class ContainerCurrentVersionSensor(PortainerContainerSensor):
    entity_suffix = "current_version"
    label = "Current Version"
    icon_name = "mdi:tag-text"

    @property
    def native_value(self):
        return self.image_value("current_version")


class ContainerAvailableVersionSensor(PortainerContainerSensor):
    entity_suffix = "available_version"
    label = "Available Version"
    icon_name = "mdi:tag-plus"

    @property
    def native_value(self):
        return self.image_value("available_version")


class ContainerCurrentDigestSensor(PortainerContainerSensor):
    entity_suffix = "current_digest"
    label = "Current Digest"
    icon_name = "mdi:fingerprint"

    @property
    def native_value(self):
        return self.image_value("current_digest")


class ContainerAvailableDigestSensor(PortainerContainerSensor):
    entity_suffix = "available_digest"
    label = "Available Digest"
    icon_name = "mdi:fingerprint"

    @property
    def native_value(self):
        return self.image_value("available_digest")
