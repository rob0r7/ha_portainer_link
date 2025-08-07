import logging
from homeassistant.helpers.entity import Entity
from homeassistant.const import STATE_UNKNOWN
from .const import DOMAIN
from .portainer_api import PortainerAPI

_LOGGER = logging.getLogger(__name__)
_LOGGER.info("Loaded Portainer sensor integration.")

<<<<<<< Updated upstream
=======
def _get_host_display_name(base_url):
    """Extract a clean host name from the base URL for display purposes."""
    # Remove protocol and common ports
    host = base_url.replace("https://", "").replace("http://", "")
    # Remove trailing slash if present
    host = host.rstrip("/")
    # Remove common ports
    for port in [":9000", ":9443", ":80", ":443"]:
        if host.endswith(port):
            host = host[:-len(port)]
    
    # If the host is an IP address, keep it as is
    # If it's a domain, try to extract a meaningful name
    if host.replace('.', '').replace('-', '').replace('_', '').isdigit():
        # It's an IP address, keep as is
        return host
    else:
        # It's a domain, extract the main part
        parts = host.split('.')
        if len(parts) >= 2:
            # Use the main domain part (e.g., "portainer" from "portainer.example.com")
            return parts[0]
        else:
            return host

def _get_host_hash(base_url):
    """Generate a short hash of the host URL for unique identification."""
    return hashlib.md5(base_url.encode()).hexdigest()[:8]

def _get_simple_device_id(entry_id, endpoint_id, host_name, container_or_stack_name):
    """Generate a simple, predictable device ID."""
    # Use a simple format: entry_endpoint_host_container
    sanitized_host = host_name.replace('.', '_').replace(':', '_').replace('-', '_')
    sanitized_name = container_or_stack_name.replace('-', '_').replace(' ', '_')
    return f"{entry_id}_{endpoint_id}_{sanitized_host}_{sanitized_name}"

>>>>>>> Stashed changes
async def async_setup_entry(hass, entry, async_add_entities):
    config = entry.data
    host = config["host"]
    username = config.get("username")
    password = config.get("password")
    api_key = config.get("api_key")
    endpoint_id = config["endpoint_id"]

    api = PortainerAPI(host, username, password, api_key)
    await api.initialize()
    containers = await api.get_containers(endpoint_id)

    entities = []
    for container in containers:
        name = container.get("Names", ["unknown"])[0].strip("/")
        container_id = container["Id"]
        state = container.get("State", STATE_UNKNOWN)

<<<<<<< Updated upstream
        entities.append(ContainerStatusSensor(name, state, api, endpoint_id, container_id))
        entities.append(ContainerCPUSensor(name, api, endpoint_id, container_id))
        entities.append(ContainerMemorySensor(name, api, endpoint_id, container_id))
        entities.append(ContainerUptimeSensor(name, api, endpoint_id, container_id))
        entities.append(ContainerImageSensor(name, container, api, endpoint_id, container_id))
        entities.append(ContainerCurrentVersionSensor(name, api, endpoint_id, container_id))
        entities.append(ContainerAvailableVersionSensor(name, api, endpoint_id, container_id))
=======
        # Create sensors for all containers - they will all belong to the same stack device if they're in a stack
        entities.append(ContainerStatusSensor(name, container_id, api, endpoint_id, stack_info, entry_id))
        entities.append(ContainerCPUSensor(name, container_id, api, endpoint_id, stack_info, entry_id))
        entities.append(ContainerMemorySensor(name, container_id, api, endpoint_id, stack_info, entry_id))
        entities.append(ContainerUptimeSensor(name, container_id, api, endpoint_id, stack_info, entry_id))
        entities.append(ContainerImageSensor(name, container_id, api, endpoint_id, stack_info, entry_id))
        entities.append(ContainerCurrentVersionSensor(name, container_id, api, endpoint_id, stack_info, entry_id))
        entities.append(ContainerAvailableVersionSensor(name, container_id, api, endpoint_id, stack_info, entry_id))

    _LOGGER.info("✅ Created %d entities (%d stack containers, %d standalone containers)", 
                len(entities), stack_containers_count, standalone_containers_count)
>>>>>>> Stashed changes

    async_add_entities(entities, update_before_add=True)

class BaseContainerSensor(Entity):
    """Base class for all container sensors."""

    def __init__(self, container_name, container_id, api):
        self._container_name = container_name
        self._container_id = container_id
        self._api = api

    @property
    def device_info(self):
<<<<<<< Updated upstream
        return {
            "identifiers": {(DOMAIN, self._container_id)},
            "name": self._container_name,
            "manufacturer": "Docker via Portainer",
            "model": "Docker Container",
            "configuration_url": f"{self._api.base_url}/#!/containers/{self._container_id}/details",
        }
=======
        host_name = _get_host_display_name(self._api.base_url)
        
        if self._stack_info.get("is_stack_container"):
            # For stack containers, use the stack as the device
            stack_name = self._stack_info.get("stack_name", "unknown_stack")
            device_id = _get_simple_device_id(self._entry_id, self._endpoint_id, host_name, f"stack_{stack_name}")
            _LOGGER.debug("🏗️ Creating stack device: %s (ID: %s) for host: %s", 
                        stack_name, device_id, host_name)
            return {
                "identifiers": {(DOMAIN, device_id)},
                "name": f"Stack: {stack_name} ({host_name})",
                "manufacturer": "Docker via Portainer",
                "model": "Docker Stack",
                "configuration_url": f"{self._api.base_url}/#!/stacks/{stack_name}",
            }
        else:
            # For standalone containers, use the container as the device
            device_id = _get_simple_device_id(self._entry_id, self._endpoint_id, host_name, self._container_name)
            _LOGGER.debug("🏗️ Creating standalone container device: %s (ID: %s) for host: %s", 
                        self._container_name, device_id, host_name)
            return {
                "identifiers": {(DOMAIN, device_id)},
                "name": f"{self._container_name} ({host_name})",
                "manufacturer": "Docker via Portainer",
                "model": "Docker Container",
                "configuration_url": f"{self._api.base_url}/#!/containers/{self._container_id}/details",
            }
>>>>>>> Stashed changes

class ContainerStatusSensor(BaseContainerSensor):
    """Sensor for container status."""

<<<<<<< Updated upstream
    def __init__(self, name, state, api, endpoint_id, container_id):
        super().__init__(name, container_id, api)
        self._attr_name = f"{name} Status"
        self._attr_unique_id = f"{container_id}_status"
        self._endpoint_id = endpoint_id
        self._state = state
=======
    def __init__(self, container_name, container_id, api, endpoint_id, stack_info, entry_id):
        super().__init__(container_name, container_id, api, endpoint_id, stack_info, entry_id)
        self._attr_unique_id = f"entry_{entry_id}_endpoint_{endpoint_id}_{container_id}_status"
        self._state = STATE_UNKNOWN
        # Improve naming for stack containers
        if stack_info.get("is_stack_container"):
            stack_name = stack_info.get("stack_name", "unknown")
            service_name = stack_info.get("service_name", container_name)
            self._attr_name = f"{service_name} Status ({stack_name})"
        else:
            self._attr_name = f"{container_name} Status"
>>>>>>> Stashed changes

    @property
    def state(self):
        return self._state or STATE_UNKNOWN

    @property
    def icon(self):
        return {
            "running": "mdi:docker",
            "exited": "mdi:close-circle",
            "paused": "mdi:pause-circle",
        }.get(self._state, "mdi:help-circle")

    async def async_update(self):
        """Update the container status."""
        try:
            container_info = await self._api.get_container_info(self._endpoint_id, self._container_id)
            if container_info:
                self._state = container_info.get("State", {}).get("Status", STATE_UNKNOWN)
            else:
                self._state = STATE_UNKNOWN
        except Exception as e:
            _LOGGER.warning("Failed to get status for %s: %s", self._attr_name, e)
            self._state = STATE_UNKNOWN

class ContainerCPUSensor(BaseContainerSensor):
    """Sensor for container CPU usage."""

<<<<<<< Updated upstream
    def __init__(self, name, api, endpoint_id, container_id):
        super().__init__(name, container_id, api)
        self._attr_name = f"{name} CPU Usage"
        self._attr_unique_id = f"{container_id}_cpu_usage"
        self._endpoint_id = endpoint_id
        self._state = STATE_UNKNOWN
=======
    def __init__(self, container_name, container_id, api, endpoint_id, stack_info, entry_id):
        super().__init__(container_name, container_id, api, endpoint_id, stack_info, entry_id)
        self._attr_unique_id = f"entry_{entry_id}_endpoint_{endpoint_id}_{container_id}_cpu_usage"
        # Improve naming for stack containers
        if stack_info.get("is_stack_container"):
            stack_name = stack_info.get("stack_name", "unknown")
            service_name = stack_info.get("service_name", container_name)
            self._attr_name = f"{service_name} CPU Usage ({stack_name})"
        else:
            self._attr_name = f"{container_name} CPU Usage"
>>>>>>> Stashed changes

    @property
    def state(self):
        return self._state

    @property
    def unit_of_measurement(self):
        return "%"

    @property
    def icon(self):
        return "mdi:cpu-64-bit"

    async def async_update(self):
        stats = await self._api.get_container_stats(self._endpoint_id, self._container_id)
        try:
            cpu_usage = stats["cpu_stats"]["cpu_usage"]["total_usage"]
            precpu_usage = stats["precpu_stats"]["cpu_usage"]["total_usage"]
            system_cpu = stats["cpu_stats"]["system_cpu_usage"]
            pre_system_cpu = stats["precpu_stats"]["system_cpu_usage"]

            cpu_delta = cpu_usage - precpu_usage
            system_delta = system_cpu - pre_system_cpu
            cpu_count = stats.get("cpu_stats", {}).get("online_cpus", 1)

            usage = (cpu_delta / system_delta) * cpu_count * 100.0 if system_delta > 0 else 0
            self._state = round(usage, 2)
        except Exception as e:
            _LOGGER.warning("Failed to parse CPU stats for %s: %s", self._attr_name, e)
            self._state = STATE_UNKNOWN

class ContainerMemorySensor(BaseContainerSensor):
    """Sensor for container memory usage."""

<<<<<<< Updated upstream
    def __init__(self, name, api, endpoint_id, container_id):
        super().__init__(name, container_id, api)
        self._attr_name = f"{name} Memory Usage"
        self._attr_unique_id = f"{container_id}_memory_usage"
        self._endpoint_id = endpoint_id
        self._state = STATE_UNKNOWN
=======
    def __init__(self, container_name, container_id, api, endpoint_id, stack_info, entry_id):
        super().__init__(container_name, container_id, api, endpoint_id, stack_info, entry_id)
        self._attr_unique_id = f"entry_{entry_id}_endpoint_{endpoint_id}_{container_id}_memory_usage"
        # Improve naming for stack containers
        if stack_info.get("is_stack_container"):
            stack_name = stack_info.get("stack_name", "unknown")
            service_name = stack_info.get("service_name", container_name)
            self._attr_name = f"{service_name} Memory Usage ({stack_name})"
        else:
            self._attr_name = f"{container_name} Memory Usage"
>>>>>>> Stashed changes

    @property
    def state(self):
        return self._state

    @property
    def unit_of_measurement(self):
        return "MB"

    @property
    def icon(self):
        return "mdi:memory"

    async def async_update(self):
        stats = await self._api.get_container_stats(self._endpoint_id, self._container_id)
        try:
            mem_bytes = stats["memory_stats"]["usage"]
            self._state = round(mem_bytes / (1024 * 1024), 2)
        except Exception as e:
            _LOGGER.warning("Failed to parse memory stats for %s: %s", self._attr_name, e)
            self._state = STATE_UNKNOWN

class ContainerUptimeSensor(BaseContainerSensor):
    """Sensor for container uptime."""

<<<<<<< Updated upstream
    def __init__(self, name, api, endpoint_id, container_id):
        super().__init__(name, container_id, api)
        self._attr_name = f"{name} Uptime"
        self._attr_unique_id = f"{container_id}_uptime"
        self._endpoint_id = endpoint_id
        self._state = STATE_UNKNOWN
=======
    def __init__(self, container_name, container_id, api, endpoint_id, stack_info, entry_id):
        super().__init__(container_name, container_id, api, endpoint_id, stack_info, entry_id)
        self._attr_unique_id = f"entry_{entry_id}_endpoint_{endpoint_id}_{container_id}_uptime"
        # Improve naming for stack containers
        if stack_info.get("is_stack_container"):
            stack_name = stack_info.get("stack_name", "unknown")
            service_name = stack_info.get("service_name", container_name)
            self._attr_name = f"{service_name} Uptime ({stack_name})"
        else:
            self._attr_name = f"{container_name} Uptime"
>>>>>>> Stashed changes

    @property
    def state(self):
        return self._state

    @property
    def icon(self):
        return "mdi:clock-outline"

    async def async_update(self):
        container_info = await self._api.get_container_info(self._endpoint_id, self._container_id)
        try:
            started_at = container_info["State"]["StartedAt"]
            if started_at and started_at != "0001-01-01T00:00:00Z":
                # Convert ISO timestamp to human readable format
                from datetime import datetime
                try:
                    dt = datetime.fromisoformat(started_at.replace('Z', '+00:00'))
                    # Format as relative time (e.g., "2 days ago")
                    from datetime import timezone
                    now = datetime.now(timezone.utc)
                    diff = now - dt.replace(tzinfo=timezone.utc)
                    
                    if diff.days > 0:
                        self._state = f"{diff.days} days ago"
                    elif diff.seconds > 3600:
                        hours = diff.seconds // 3600
                        self._state = f"{hours} hours ago"
                    elif diff.seconds > 60:
                        minutes = diff.seconds // 60
                        self._state = f"{minutes} minutes ago"
                    else:
                        self._state = "Just started"
                except:
                    # Fallback to original format if parsing fails
                    self._state = started_at
            else:
                self._state = "Not started"
        except Exception as e:
            _LOGGER.warning("Failed to get uptime for %s: %s", self._attr_name, e)
            self._state = STATE_UNKNOWN

class ContainerImageSensor(BaseContainerSensor):
    """Sensor for container image."""

<<<<<<< Updated upstream
    def __init__(self, name, container_data, api, endpoint_id, container_id):
        super().__init__(name, container_id, api)
        self._attr_name = f"{name} Image"
        self._attr_unique_id = f"{container_id}_image"
        self._endpoint_id = endpoint_id
        self._state = container_data.get("Image", STATE_UNKNOWN)
=======
    def __init__(self, container_name, container_id, api, endpoint_id, stack_info, entry_id):
        super().__init__(container_name, container_id, api, endpoint_id, stack_info, entry_id)
        self._attr_unique_id = f"entry_{entry_id}_endpoint_{endpoint_id}_{container_id}_image"
        # Improve naming for stack containers
        if stack_info.get("is_stack_container"):
            stack_name = stack_info.get("stack_name", "unknown")
            service_name = stack_info.get("service_name", container_name)
            self._attr_name = f"{service_name} Image ({stack_name})"
        else:
            self._attr_name = f"{container_name} Image"
>>>>>>> Stashed changes

    @property
    def state(self):
        return self._state

    @property
    def icon(self):
        return "mdi:docker"

    async def async_update(self):
        """Update the container image information."""
        try:
            container_info = await self._api.get_container_info(self._endpoint_id, self._container_id)
            if container_info:
                self._state = container_info.get("Config", {}).get("Image", STATE_UNKNOWN)
            else:
                self._state = STATE_UNKNOWN
        except Exception as e:
            _LOGGER.warning("Failed to get image for %s: %s", self._attr_name, e)
            self._state = STATE_UNKNOWN


class ContainerCurrentVersionSensor(BaseContainerSensor):
    """Sensor for container current version."""

<<<<<<< Updated upstream
    def __init__(self, name, api, endpoint_id, container_id):
        super().__init__(name, container_id, api)
        self._attr_name = f"{name} Current Version"
        self._attr_unique_id = f"{container_id}_current_version"
        self._endpoint_id = endpoint_id
        self._state = STATE_UNKNOWN
=======
    def __init__(self, container_name, container_id, api, endpoint_id, stack_info, entry_id):
        super().__init__(container_name, container_id, api, endpoint_id, stack_info, entry_id)
        self._attr_unique_id = f"entry_{entry_id}_endpoint_{endpoint_id}_{container_id}_current_version"
        # Improve naming for stack containers
        if stack_info.get("is_stack_container"):
            stack_name = stack_info.get("stack_name", "unknown")
            service_name = stack_info.get("service_name", container_name)
            self._attr_name = f"{service_name} Current Version ({stack_name})"
        else:
            self._attr_name = f"{container_name} Current Version"
>>>>>>> Stashed changes

    @property
    def state(self):
        return self._state

    @property
    def icon(self):
        return "mdi:tag-text"

    async def async_update(self):
        try:
            container_info = await self._api.get_container_info(self._endpoint_id, self._container_id)
            if container_info:
                image_id = container_info.get("Image")
                if image_id:
                    # Get image details to extract version info
                    image_data = await self._api.get_image_info(self._endpoint_id, image_id)
                    if image_data:
                        version = self._api.extract_version_from_image(image_data)
                        self._state = version
                    else:
                        self._state = STATE_UNKNOWN
                else:
                    self._state = STATE_UNKNOWN
            else:
                self._state = STATE_UNKNOWN
        except Exception as e:
            _LOGGER.warning("Failed to get current version for %s: %s", self._attr_name, e)
            self._state = STATE_UNKNOWN


class ContainerAvailableVersionSensor(BaseContainerSensor):
    """Sensor for container available version."""

<<<<<<< Updated upstream
    def __init__(self, name, api, endpoint_id, container_id):
        super().__init__(name, container_id, api)
        self._attr_name = f"{name} Available Version"
        self._attr_unique_id = f"{container_id}_available_version"
        self._endpoint_id = endpoint_id
        self._state = STATE_UNKNOWN
=======
    def __init__(self, container_name, container_id, api, endpoint_id, stack_info, entry_id):
        super().__init__(container_name, container_id, api, endpoint_id, stack_info, entry_id)
        self._attr_unique_id = f"entry_{entry_id}_endpoint_{endpoint_id}_{container_id}_available_version"
        # Improve naming for stack containers
        if stack_info.get("is_stack_container"):
            stack_name = stack_info.get("stack_name", "unknown")
            service_name = stack_info.get("service_name", container_name)
            self._attr_name = f"{service_name} Available Version ({stack_name})"
        else:
            self._attr_name = f"{container_name} Available Version"
>>>>>>> Stashed changes

    @property
    def state(self):
        return self._state

    @property
    def icon(self):
        return "mdi:tag-plus"

    async def async_update(self):
        try:
            container_info = await self._api.get_container_info(self._endpoint_id, self._container_id)
            if container_info:
                image_name = container_info.get("Config", {}).get("Image")
                if image_name:
                    # Get available version from registry
                    available_version = await self._api.get_available_version(self._endpoint_id, image_name)
                    self._state = available_version
                else:
                    self._state = STATE_UNKNOWN
            else:
                self._state = STATE_UNKNOWN
        except Exception as e:
            _LOGGER.warning("Failed to get available version for %s: %s", self._attr_name, e)
            self._state = STATE_UNKNOWN