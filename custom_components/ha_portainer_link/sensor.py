import logging
from homeassistant.const import STATE_UNKNOWN, PERCENTAGE, UnitOfInformation, UnitOfTime
from homeassistant.components.sensor import SensorEntity, SensorDeviceClass
from homeassistant.helpers.entity import EntityCategory

from .const import DOMAIN
from .entity import BaseContainerEntity, BaseStackEntity
from .coordinator import PortainerDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)
_LOGGER.info("Loaded Portainer sensor integration.")

async def async_setup_entry(hass, entry, async_add_entities):
    config = dict(entry.data)  # Create mutable copy
    endpoint_id = config["endpoint_id"]
    entry_id = entry.entry_id

    _LOGGER.info("🚀 Setting up HA Portainer Link sensors for entry %s (endpoint %s)", entry_id, endpoint_id)
    
    # Get coordinator
    coordinator = hass.data[DOMAIN][f"{entry_id}_coordinator"]
    
    # Check if sensors are enabled using coordinator
    resource_sensors_enabled = coordinator.is_resource_sensors_enabled()
    version_sensors_enabled = coordinator.is_version_sensors_enabled()
    
    _LOGGER.info("📊 Sensor configuration: Resource sensors=%s, Version sensors=%s", 
                 resource_sensors_enabled, version_sensors_enabled)
    
    # Always create status sensors (core functionality). If other sensors are disabled, only status sensors will be created.
    any_sensors_enabled = resource_sensors_enabled or version_sensors_enabled or coordinator.is_stack_view_enabled()
    if not any_sensors_enabled:
        _LOGGER.info("ℹ️ Only status sensors will be created (other sensor types disabled)")
    
    # Coordinator data is already loaded in main setup
    entities = []
    
    # Track which containers we've already created sensor entities for (by container_id)
    created_for: set[str] = set()
    
    # Helper to create all sensors for a single container
    def _create_container_sensors(container_id: str, container_data: dict) -> list:
        container_name = container_data.get("Names", ["unknown"])[0].strip("/")
        stack_info = coordinator.get_container_stack_info(container_id) or {
            "stack_name": None,
            "service_name": None,
            "container_number": None,
            "is_stack_container": False
        }
        _LOGGER.debug("🔍 Processing container: %s (ID: %s, Stack: %s)", container_name, container_id, stack_info.get("stack_name"))
        new_entities = []
        # Always create status sensor (core functionality)
        new_entities.append(ContainerStatusSensor(coordinator, entry_id, container_id, container_name, stack_info))
        # Resource sensors
        if resource_sensors_enabled:
            new_entities.append(ContainerCPUSensor(coordinator, entry_id, container_id, container_name, stack_info))
            new_entities.append(ContainerMemorySensor(coordinator, entry_id, container_id, container_name, stack_info))
            new_entities.append(ContainerUptimeSensor(coordinator, entry_id, container_id, container_name, stack_info))
        # Version/image sensors
        if version_sensors_enabled:
            new_entities.append(ContainerImageSensor(coordinator, entry_id, container_id, container_name, stack_info))
            new_entities.append(ContainerCurrentVersionSensor(coordinator, entry_id, container_id, container_name, stack_info))
            new_entities.append(ContainerAvailableVersionSensor(coordinator, entry_id, container_id, container_name, stack_info))
            new_entities.append(ContainerCurrentDigestSensor(coordinator, entry_id, container_id, container_name, stack_info))
            new_entities.append(ContainerAvailableDigestSensor(coordinator, entry_id, container_id, container_name, stack_info))
        return new_entities
    
    # Initial creation for all known containers
    for container_id, container_data in coordinator.containers.items():
        entities.extend(_create_container_sensors(container_id, container_data))
        created_for.add(container_id)

    # Create stack-level sensors if stack view is enabled
    created_stacks: set[str] = set()
    if coordinator.is_stack_view_enabled():
        for stack_name, stack_data in coordinator.stacks.items():
            _LOGGER.debug("🔍 Creating stack sensors for: %s", stack_name)
            entities.append(StackStatusSensor(coordinator, entry_id, stack_name))
            entities.append(StackContainerCountSensor(coordinator, entry_id, stack_name))
            created_stacks.add(stack_name)
    
    _LOGGER.info("✅ Created %d sensor entities", len(entities))
    # Register immediately; values will populate on next coordinator refresh
    async_add_entities(entities, update_before_add=False)

    # Dynamically add sensors for newly discovered containers and stacks on future updates
    def _add_new_entities() -> None:
        new_entities: list = []
        # Containers
        for container_id, container_data in coordinator.containers.items():
            if container_id not in created_for:
                _LOGGER.info("➕ Discovered new container %s, creating sensors", container_id)
                new_entities.extend(_create_container_sensors(container_id, container_data))
                created_for.add(container_id)
        # Stacks
        if coordinator.is_stack_view_enabled():
            for stack_name in coordinator.stacks.keys():
                if stack_name not in created_stacks:
                    _LOGGER.info("➕ Discovered new stack %s, creating sensors", stack_name)
                    new_entities.append(StackStatusSensor(coordinator, entry_id, stack_name))
                    new_entities.append(StackContainerCountSensor(coordinator, entry_id, stack_name))
                    created_stacks.add(stack_name)
        if new_entities:
            async_add_entities(new_entities, update_before_add=False)

    # Listen for coordinator updates to discover new containers and stacks
    coordinator.async_add_listener(_add_new_entities)

class ContainerStatusSensor(BaseContainerEntity, SensorEntity):
    """Sensor for container status."""

    @property
    def entity_type(self) -> str:
        return "status"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        display_name = self._get_container_name_display()
        if self.stack_info.get("is_stack_container"):
            return f"Container Status {display_name}"
        else:
            return f"Status {display_name}"

    @property
    def native_value(self):
        """Return a normalized container state string."""
        container_data = self._get_container_data()
        if not container_data:
            return STATE_UNKNOWN
        raw_state = container_data.get("State")
        if isinstance(raw_state, dict):
            if raw_state.get("Running") is True:
                return "running"
            status_text = raw_state.get("Status") or raw_state.get("State")
            if isinstance(status_text, str) and status_text:
                return status_text
            return "exited"
        if isinstance(raw_state, str):
            return raw_state
        return STATE_UNKNOWN

    @property
    def icon(self):
        return {
            "running": "mdi:docker",
            "exited": "mdi:close-circle",
            "paused": "mdi:pause-circle",
        }.get(self.native_value, "mdi:help-circle")

    @property
    def entity_category(self) -> EntityCategory | None:
        return EntityCategory.DIAGNOSTIC

class ContainerCPUSensor(BaseContainerEntity, SensorEntity):
    """Sensor for container CPU usage."""

    @property
    def entity_type(self) -> str:
        return "cpu_usage"

    @property
    def name(self) -> str:
        display_name = self._get_container_name_display()
        return f"Container CPU {display_name}" if self.stack_info.get("is_stack_container") else f"CPU {display_name}"

    @property
    def native_value(self):
        metrics = self.coordinator.metrics.get(self.container_id, {})
        return metrics.get("cpu_percent", STATE_UNKNOWN)

    @property
    def native_unit_of_measurement(self):
        return PERCENTAGE

    @property
    def device_class(self):
        return SensorDeviceClass.POWER_FACTOR  # closest for percentage display in HA

    @property
    def icon(self):
        return "mdi:cpu-64-bit"

    @property
    def entity_category(self) -> EntityCategory | None:
        return EntityCategory.DIAGNOSTIC

class ContainerMemorySensor(BaseContainerEntity, SensorEntity):
    """Sensor for container memory usage."""

    @property
    def entity_type(self) -> str:
        return "memory_usage"

    @property
    def name(self) -> str:
        display_name = self._get_container_name_display()
        return f"Container Memory {display_name}" if self.stack_info.get("is_stack_container") else f"Memory {display_name}"

    @property
    def native_value(self):
        metrics = self.coordinator.metrics.get(self.container_id, {})
        return metrics.get("memory_mb", STATE_UNKNOWN)

    @property
    def native_unit_of_measurement(self):
        return UnitOfInformation.MEGABYTES

    @property
    def device_class(self):
        return SensorDeviceClass.DATA_SIZE

    @property
    def icon(self):
        return "mdi:memory"

    @property
    def entity_category(self) -> EntityCategory | None:
        return EntityCategory.DIAGNOSTIC

class ContainerUptimeSensor(BaseContainerEntity, SensorEntity):
    """Sensor for container uptime."""

    @property
    def entity_type(self) -> str:
        return "uptime"

    @property
    def name(self) -> str:
        display_name = self._get_container_name_display()
        return f"Container Uptime {display_name}" if self.stack_info.get("is_stack_container") else f"Uptime {display_name}"

    @property
    def native_value(self):
        metrics = self.coordinator.metrics.get(self.container_id, {})
        return metrics.get("uptime_s", STATE_UNKNOWN)

    @property
    def native_unit_of_measurement(self):
        return UnitOfTime.SECONDS

    @property
    def device_class(self):
        return SensorDeviceClass.DURATION

    @property
    def icon(self):
        return "mdi:clock-outline"

    @property
    def entity_category(self) -> EntityCategory | None:
        return EntityCategory.DIAGNOSTIC

class ContainerImageSensor(BaseContainerEntity, SensorEntity):
    """Sensor for container image information."""

    @property
    def entity_type(self) -> str:
        return "image"

    @property
    def name(self) -> str:
        display_name = self._get_container_name_display()
        return f"Image {display_name}"

    @property
    def native_value(self):
        data = self.coordinator.image_data.get(self.container_id, {})
        return data.get("image_name", STATE_UNKNOWN)

    @property
    def icon(self):
        return "mdi:docker"

    @property
    def entity_category(self) -> EntityCategory | None:
        return EntityCategory.DIAGNOSTIC

class ContainerCurrentVersionSensor(BaseContainerEntity, SensorEntity):
    """Sensor for container current version."""

    @property
    def entity_type(self) -> str:
        return "current_version"

    @property
    def name(self) -> str:
        display_name = self._get_container_name_display()
        return f"Current Version {display_name}"

    @property
    def native_value(self):
        data = self.coordinator.image_data.get(self.container_id, {})
        return data.get("current_version", STATE_UNKNOWN)

    @property
    def icon(self):
        return "mdi:tag"

    @property
    def entity_category(self) -> EntityCategory | None:
        return EntityCategory.DIAGNOSTIC

class ContainerAvailableVersionSensor(BaseContainerEntity, SensorEntity):
    """Sensor for container available version."""

    @property
    def entity_type(self) -> str:
        return "available_version"

    @property
    def name(self) -> str:
        display_name = self._get_container_name_display()
        if self.stack_info.get("is_stack_container"):
            return f"Container Available Version {display_name}"
        else:
            return f"Available Version {display_name}"

    @property
    def native_value(self):
        data = self.coordinator.image_data.get(self.container_id, {})
        return data.get("available_version", STATE_UNKNOWN)

    @property
    def icon(self):
        return "mdi:tag-outline"

    @property
    def entity_category(self) -> EntityCategory | None:
        return EntityCategory.DIAGNOSTIC


class ContainerCurrentDigestSensor(BaseContainerEntity, SensorEntity):
    """Sensor for current image digest."""

    @property
    def entity_type(self) -> str:
        return "current_digest"

    @property
    def name(self) -> str:
        display_name = self._get_container_name_display()
        return f"Current Digest {display_name}"

    @property
    def native_value(self):
        data = self.coordinator.image_data.get(self.container_id, {})
        return data.get("current_digest", STATE_UNKNOWN)

    @property
    def icon(self):
        return "mdi:fingerprint"

    @property
    def entity_category(self) -> EntityCategory | None:
        return EntityCategory.DIAGNOSTIC


class ContainerAvailableDigestSensor(BaseContainerEntity, SensorEntity):
    """Sensor for available image digest in registry."""

    @property
    def entity_type(self) -> str:
        return "available_digest"

    @property
    def name(self) -> str:
        display_name = self._get_container_name_display()
        return f"Available Digest {display_name}"

    @property
    def native_value(self):
        data = self.coordinator.image_data.get(self.container_id, {})
        return data.get("available_digest", STATE_UNKNOWN)

    @property
    def icon(self):
        return "mdi:fingerprint-outline"

    @property
    def entity_category(self) -> EntityCategory | None:
        return EntityCategory.DIAGNOSTIC


class StackStatusSensor(BaseStackEntity, SensorEntity):
    """Sensor for stack status."""

    @property
    def entity_type(self) -> str:
        return "stack_status"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"Stack Status {self.stack_name}"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        stack_data = self._get_stack_data()
        if stack_data:
            return stack_data.get("Status", STATE_UNKNOWN)
        return STATE_UNKNOWN

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return {
            "active": "mdi:check-circle",
            "inactive": "mdi:close-circle",
            "pending": "mdi:clock",
        }.get(self.native_value, "mdi:help-circle")

    @property
    def entity_category(self) -> EntityCategory | None:
        return EntityCategory.DIAGNOSTIC


class StackContainerCountSensor(BaseStackEntity, SensorEntity):
    """Sensor for stack container count."""

    @property
    def entity_type(self) -> str:
        return "stack_container_count"

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"Stack Container Count {self.stack_name}"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        containers = self._get_stack_containers()
        return len(containers) if containers else 0

    @property
    def icon(self):
        """Return the icon of the sensor."""
        return "mdi:docker"

    @property
    def entity_category(self) -> EntityCategory | None:
        return EntityCategory.DIAGNOSTIC