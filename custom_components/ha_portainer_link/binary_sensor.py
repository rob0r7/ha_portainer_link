import logging
from homeassistant.components.binary_sensor import BinarySensorEntity
from .const import DOMAIN
from .portainer_api import PortainerAPI
from .sensor import BaseContainerSensor

_LOGGER = logging.getLogger(__name__)
_LOGGER.info("Loaded Portainer binary sensor integration.")

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
<<<<<<< Updated upstream
        entities.append(ContainerUpdateAvailableSensor(name, api, endpoint_id, container_id))
=======
        
        # Get container inspection data to determine if it's part of a stack
        container_info = await api.inspect_container(endpoint_id, container_id)
        stack_info = api.get_container_stack_info(container_info) if container_info else {"is_stack_container": False}
        
        # Create binary sensors for all containers - they will all belong to the same stack device if they're in a stack
        entities.append(ContainerUpdateAvailableSensor(name, container_id, api, endpoint_id, stack_info, entry_id))
>>>>>>> Stashed changes

    async_add_entities(entities, update_before_add=True)


class ContainerUpdateAvailableSensor(BinarySensorEntity, BaseContainerSensor):
    """Binary sensor representing if a container has updates available."""

<<<<<<< Updated upstream
    def __init__(self, name, api, endpoint_id, container_id):
        self._attr_name = f"{name} Update Available"
        self._container_name = name
        self._api = api
        self._endpoint_id = endpoint_id
        self._container_id = container_id
        self._attr_unique_id = f"{container_id}_update_available"
=======
    def __init__(self, container_name, container_id, api, endpoint_id, stack_info, entry_id):
        BaseContainerSensor.__init__(self, container_name, container_id, api, endpoint_id, stack_info, entry_id)
        self._attr_unique_id = f"entry_{entry_id}_endpoint_{endpoint_id}_{container_id}_update_available"
>>>>>>> Stashed changes
        self._attr_is_on = False
        # Improve naming for stack containers
        if stack_info.get("is_stack_container"):
            stack_name = stack_info.get("stack_name", "unknown")
            service_name = stack_info.get("service_name", container_name)
            self._attr_name = f"{service_name} Update Available ({stack_name})"
        else:
            self._attr_name = f"{container_name} Update Available"

    @property
    def icon(self):
        return "mdi:update" if self._attr_is_on else "mdi:update-disabled"

<<<<<<< Updated upstream
    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._container_id)},
            "name": self._container_name,
            "manufacturer": "Docker via Portainer",
            "model": "Docker Container",
            "configuration_url": f"{self._api.base_url}/#!/containers/{self._container_id}/details",
        }

=======
>>>>>>> Stashed changes
    async def async_update(self):
        """Update the update availability status."""
        try:
            has_update = await self._api.check_image_updates(self._endpoint_id, self._container_id)
            self._attr_is_on = has_update
        except Exception as e:
            _LOGGER.warning("Failed to check update availability for %s: %s", self._attr_name, e)
            self._attr_is_on = False
