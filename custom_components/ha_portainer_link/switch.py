import logging
from homeassistant.components.switch import SwitchEntity
from .const import DOMAIN
from .portainer_api import PortainerAPI

_LOGGER = logging.getLogger(__name__)
_LOGGER.info("Loaded Portainer switch integration.")

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
    conf = entry.data
    host = conf["host"]
    username = conf.get("username")
    password = conf.get("password")
    api_key = conf.get("api_key")
    endpoint_id = conf["endpoint_id"]

    api = PortainerAPI(host, username, password, api_key)
    await api.initialize()
    containers = await api.get_containers(endpoint_id)

    switches = []
    for container in containers:
        name = container.get("Names", ["unknown"])[0].strip("/")
        container_id = container["Id"]
        state = container.get("State", "unknown")
        switches.append(ContainerSwitch(name, state, api, endpoint_id, container_id))

    async_add_entities(switches, update_before_add=True)

class ContainerSwitch(SwitchEntity):
    """Switch to start/stop a Docker container."""

    def __init__(self, name, state, api, endpoint_id, container_id):
        self._attr_name = f"{name} Switch"
        self._container_name = name
        self._state = state == "running"
        self._api = api
        self._endpoint_id = endpoint_id
        self._container_id = container_id
        self._attr_unique_id = f"{container_id}_switch"
        self._available = True

    @property
    def is_on(self):
        return self._state is True

    @property
    def available(self):
        return self._available

    @property
    def icon(self):
        return "mdi:power"

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

    async def async_turn_on(self, **kwargs):
        """Start the Docker container."""
        success = await self._api.start_container(self._endpoint_id, self._container_id)
        if success:
            self._state = True
            self._available = True
        else:
            self._available = False
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs):
        """Stop the Docker container."""
        success = await self._api.stop_container(self._endpoint_id, self._container_id)
        if success:
            self._state = False
            self._available = True
        else:
            self._available = False
        self.async_write_ha_state()

    async def async_update(self):
        """Update the current status of the container."""
        try:
            containers = await self._api.get_containers(self._endpoint_id)
            for container in containers:
                if container["Id"] == self._container_id:
                    self._state = container.get("State") == "running"
                    self._available = True
                    return
            self._state = False
            self._available = False
        except Exception as e:
            _LOGGER.error("Failed to update status for %s: %s", self._container_name, e)
            self._available = False
