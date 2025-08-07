import logging
import hashlib
from homeassistant.helpers.entity import Entity
from homeassistant.const import STATE_UNKNOWN
from .const import DOMAIN
from .portainer_api import PortainerAPI

_LOGGER = logging.getLogger(__name__)
_LOGGER.info("Loaded Portainer sensor integration.")

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

async def async_setup_entry(hass, entry, async_add_entities):
    config = entry.data
    host = config["host"]
    username = config.get("username")
    password = config.get("password")
    api_key = config.get("api_key")
    endpoint_id = config["endpoint_id"]
    entry_id = entry.entry_id

    _LOGGER.info("🚀 Setting up HA Portainer Link sensors for entry %s (endpoint %s)", entry_id, endpoint_id)
    _LOGGER.info("📍 Portainer host: %s", host)
    
    # Log the extracted host name for debugging
    host_display_name = _get_host_display_name(host)
    _LOGGER.info("🏷️ Extracted host display name: %s", host_display_name)

    api = PortainerAPI(host, username, password, api_key)
    await api.initialize()
    containers = await api.get_containers(endpoint_id)

    _LOGGER.info("📦 Found %d containers to process", len(containers))

    entities = []
    stack_containers_count = 0
    standalone_containers_count = 0
    
    for container in containers:
        name = container.get("Names", ["unknown"])[0].strip("/")
        container_id = container["Id"]
        state = container.get("State", STATE_UNKNOWN)
        
        _LOGGER.debug("🔍 Processing container: %s (ID: %s, State: %s)", name, container_id, state)
        
        # Get container inspection data to determine if it's part of a stack
        container_info = await api.inspect_container(endpoint_id, container_id)
        stack_info = api.get_container_stack_info(container_info) if container_info else {"is_stack_container": False}
        
        if stack_info.get("is_stack_container"):
            stack_containers_count += 1
            _LOGGER.info("📋 Container %s is part of stack: %s", name, stack_info.get("stack_name"))
        else:
            standalone_containers_count += 1
            _LOGGER.info("📦 Container %s is standalone", name)

        # Create sensors for all containers - they will all belong to the same stack device if they're in a stack
        entities.append(ContainerStatusSensor(name, state, api, endpoint_id, container_id, stack_info, entry_id))
        entities.append(ContainerCPUSensor(name, api, endpoint_id, container_id, stack_info, entry_id))
        entities.append(ContainerMemorySensor(name, api, endpoint_id, container_id, stack_info, entry_id))
        entities.append(ContainerUptimeSensor(name, api, endpoint_id, container_id, stack_info, entry_id))
        entities.append(ContainerImageSensor(name, container, api, endpoint_id, container_id, stack_info, entry_id))
        entities.append(ContainerCurrentVersionSensor(name, api, endpoint_id, container_id, stack_info, entry_id))
        entities.append(ContainerAvailableVersionSensor(name, api, endpoint_id, container_id, stack_info, entry_id))

    _LOGGER.info("✅ Created %d entities (%d stack containers, %d standalone containers)", 
                len(entities), stack_containers_count, standalone_containers_count)

    async_add_entities(entities, update_before_add=True)

class BaseContainerSensor(Entity):
    """Base class for all container sensors."""

    def __init__(self, container_name, container_id, api, endpoint_id, stack_info, entry_id):
        self._container_name = container_name
        self._container_id = container_id
        self._api = api
        self._endpoint_id = endpoint_id
        self._stack_info = stack_info
        self._entry_id = entry_id

    @property
    def device_info(self):
        host_name = _get_host_display_name(self._api.base_url)
        host_hash = _get_host_hash(self._api.base_url)
        
        if self._stack_info.get("is_stack_container"):
            # For stack containers, use the stack as the device
            stack_name = self._stack_info.get("stack_name", "unknown_stack")
            # Use a more robust identifier that includes the entry_id, host hash, and host name to prevent duplicates
            device_id = f"entry_{self._entry_id}_endpoint_{self._endpoint_id}_stack_{stack_name}_{host_hash}_{host_name.replace('.', '_').replace(':', '_')}"
            _LOGGER.debug("🏗️ Creating stack device: %s (ID: %s) for host: %s (entry: %s, endpoint: %s, hash: %s)", 
                         stack_name, device_id, host_name, self._entry_id, self._endpoint_id, host_hash)
            return {
                "identifiers": {(DOMAIN, device_id)},
                "name": f"Stack: {stack_name} ({host_name})",
                "manufacturer": "Docker via Portainer",
                "model": "Docker Stack",
                "configuration_url": f"{self._api.base_url}/#!/stacks/{stack_name}",
            }
        else:
            # For standalone containers, use the container as the device
            device_id = f"entry_{self._entry_id}_endpoint_{self._endpoint_id}_container_{self._container_id}_{host_hash}_{host_name.replace('.', '_').replace(':', '_')}"
            _LOGGER.debug("🏗️ Creating standalone container device: %s (ID: %s) for host: %s (entry: %s, endpoint: %s, hash: %s)", 
                         self._container_name, device_id, host_name, self._entry_id, self._endpoint_id, host_hash)
            return {
                "identifiers": {(DOMAIN, device_id)},
                "name": f"{self._container_name} ({host_name})",
                "manufacturer": "Docker via Portainer",
                "model": "Docker Container",
                "configuration_url": f"{self._api.base_url}/#!/containers/{self._container_id}/details",
            }

class ContainerStatusSensor(BaseContainerSensor):
    """Sensor representing the status of a Docker container."""

    def __init__(self, name, state, api, endpoint_id, container_id, stack_info, entry_id):
        super().__init__(name, container_id, api, endpoint_id, stack_info, entry_id)
        self._attr_name = f"{name} Status"
        self._attr_unique_id = f"entry_{entry_id}_endpoint_{endpoint_id}_{container_id}_status"
        self._state = state

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
    """Sensor representing CPU usage of a Docker container."""

    def __init__(self, name, api, endpoint_id, container_id, stack_info, entry_id):
        super().__init__(name, container_id, api, endpoint_id, stack_info, entry_id)
        self._attr_name = f"{name} CPU Usage"
        self._attr_unique_id = f"entry_{entry_id}_endpoint_{endpoint_id}_{container_id}_cpu_usage"
        self._state = STATE_UNKNOWN

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
    """Sensor representing memory usage of a Docker container."""

    def __init__(self, name, api, endpoint_id, container_id, stack_info, entry_id):
        super().__init__(name, container_id, api, endpoint_id, stack_info, entry_id)
        self._attr_name = f"{name} Memory Usage"
        self._attr_unique_id = f"entry_{entry_id}_endpoint_{endpoint_id}_{container_id}_memory_usage"
        self._state = STATE_UNKNOWN

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
    """Sensor representing uptime of a Docker container."""

    def __init__(self, name, api, endpoint_id, container_id, stack_info, entry_id):
        super().__init__(name, container_id, api, endpoint_id, stack_info, entry_id)
        self._attr_name = f"{name} Uptime"
        self._attr_unique_id = f"entry_{entry_id}_endpoint_{endpoint_id}_{container_id}_uptime"
        self._state = STATE_UNKNOWN

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
    """Sensor representing Docker image of a container."""

    def __init__(self, name, container_data, api, endpoint_id, container_id, stack_info, entry_id):
        super().__init__(name, container_id, api, endpoint_id, stack_info, entry_id)
        self._attr_name = f"{name} Image"
        self._attr_unique_id = f"entry_{entry_id}_endpoint_{endpoint_id}_{container_id}_image"
        self._state = container_data.get("Image", STATE_UNKNOWN)

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
    """Sensor representing the current version of a Docker container."""

    def __init__(self, name, api, endpoint_id, container_id, stack_info, entry_id):
        super().__init__(name, container_id, api, endpoint_id, stack_info, entry_id)
        self._attr_name = f"{name} Current Version"
        self._attr_unique_id = f"entry_{entry_id}_endpoint_{endpoint_id}_{container_id}_current_version"
        self._state = STATE_UNKNOWN

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
    """Sensor representing the available version of a Docker container."""

    def __init__(self, name, api, endpoint_id, container_id, stack_info, entry_id):
        super().__init__(name, container_id, api, endpoint_id, stack_info, entry_id)
        self._attr_name = f"{name} Available Version"
        self._attr_unique_id = f"entry_{entry_id}_endpoint_{endpoint_id}_{container_id}_available_version"
        self._state = STATE_UNKNOWN

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