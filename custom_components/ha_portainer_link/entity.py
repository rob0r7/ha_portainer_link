import logging
import hashlib
from typing import Optional, Dict, Any
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.update_coordinator import CoordinatorEntity
from homeassistant.core import HomeAssistant

from .const import DOMAIN
from .coordinator import PortainerDataUpdateCoordinator
from . import create_portainer_device_info, create_stack_device_info, create_container_device_info

_LOGGER = logging.getLogger(__name__)

def _get_host_display_name(base_url: str) -> str:
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

def _get_simple_device_id(entry_id: str, endpoint_id: int, host_name: str, container_or_stack_name: str) -> str:
    """Generate a simple, predictable device ID."""
    # Use a simple format: entry_endpoint_host_container
    sanitized_host = host_name.replace('.', '_').replace(':', '_').replace('-', '_')
    sanitized_name = container_or_stack_name.replace('-', '_').replace(' ', '_')
    return f"{entry_id}_{endpoint_id}_{sanitized_host}_{sanitized_name}"

def _get_stable_entity_id(entry_id: str, endpoint_id: int, container_name: str, stack_info: Dict[str, Any], entity_type: str) -> str:
    """Generate a stable entity ID that doesn't change when container is recreated."""
    # For stack containers, use stack_name + service_name
    if stack_info.get("is_stack_container"):
        stack_name = stack_info.get("stack_name", "unknown")
        service_name = stack_info.get("service_name", container_name)
        # Use stack and service name for stability
        stable_id = f"{stack_name}_{service_name}"
    else:
        # For standalone containers, use container name
        stable_id = container_name
    
    # Sanitize the stable ID
    sanitized_id = stable_id.replace('-', '_').replace(' ', '_').replace('/', '_')
    return f"entry_{entry_id}_endpoint_{endpoint_id}_{sanitized_id}_{entity_type}"

def _get_container_stable_id(container_name: str, stack_info: Dict[str, Any]) -> str:
    """Generate a stable container identifier that doesn't change when container is recreated."""
    if stack_info.get("is_stack_container"):
        stack_name = stack_info.get("stack_name", "unknown")
        service_name = stack_info.get("service_name", container_name)
        return f"{stack_name}_{service_name}"
    else:
        return container_name

class BasePortainerEntity(CoordinatorEntity):
    """Base class for all Portainer entities bound to the data update coordinator."""

    def __init__(self, coordinator: PortainerDataUpdateCoordinator, entry_id: str):
        """Initialize the base entity."""
        super().__init__(coordinator)
        self.coordinator = coordinator
        self.entry_id = entry_id
        self._attr_should_poll = False

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.coordinator.last_update_success

class BaseContainerEntity(BasePortainerEntity):
    """Base class for container-specific entities."""

    def __init__(
        self, 
        coordinator: PortainerDataUpdateCoordinator, 
        entry_id: str, 
        container_id: str, 
        container_name: str, 
        stack_info: Dict[str, Any]
    ):
        """Initialize the container entity."""
        super().__init__(coordinator, entry_id)
        self.container_id = container_id
        self.container_name = container_name
        self.stack_info = stack_info
        self.stable_container_id = _get_container_stable_id(container_name, stack_info)
        self._attr_unique_id = _get_stable_entity_id(
            entry_id, 
            coordinator.endpoint_id, 
            container_name, 
            stack_info, 
            self.entity_type
        )

    @property
    def entity_type(self) -> str:
        """Return the entity type for unique ID generation."""
        raise NotImplementedError

    def update_container_id(self, new_container_id: str) -> None:
        """Update the container ID when container is recreated."""
        if new_container_id != self.container_id:
            _LOGGER.info("🔄 Updating container ID for %s: %s -> %s", 
                        self.container_name, self.container_id[:12], new_container_id[:12])
            self.container_id = new_container_id

    def _find_current_container_id(self) -> Optional[str]:
        """Find the current container ID for this entity based on stable ID."""
        # Use coordinator's stable container map if available
        if hasattr(self.coordinator, 'get_container_by_stable_id'):
            current_container_id = self.coordinator.get_container_by_stable_id(self.stable_container_id)
            if current_container_id:
                return current_container_id
        
        # Fallback: search through all containers
        for container_id, container_data in self.coordinator.containers.items():
            container_name = container_data.get("Names", ["unknown"])[0].strip("/")
            stack_info = self.coordinator.get_container_stack_info(container_id) or {
                "stack_name": None,
                "service_name": None,
                "container_number": None,
                "is_stack_container": False
            }
            stable_id = _get_container_stable_id(container_name, stack_info)
            if stable_id == self.stable_container_id:
                return container_id
        return None

    def _get_container_data(self) -> Optional[Dict[str, Any]]:
        """Get current container data from coordinator."""
        # First try the stored container ID
        container_data = self.coordinator.get_container(self.container_id)
        if container_data:
            return container_data
        
        # If not found, try to find the current container ID
        current_container_id = self._find_current_container_id()
        if current_container_id:
            self.update_container_id(current_container_id)
            return self.coordinator.get_container(current_container_id)
        
        return None

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device info."""
        host_name = _get_host_display_name(self.coordinator.api.base_url)
        
        if self.stack_info.get("is_stack_container"):
            # For stack containers, use the stack as the parent device
            stack_name = self.stack_info.get("stack_name", "unknown_stack")
            stack_id = self.stack_info.get("stack_id", stack_name)
            return create_stack_device_info(self.entry_id, stack_id, stack_name)
        else:
            # For standalone containers, use the container as the device
            return create_container_device_info(self.entry_id, self.container_id, self.container_name, self.stack_info)

    def _get_container_name_display(self) -> str:
        """Get display name for the container."""
        if self.stack_info.get("is_stack_container"):
            service_name = self.stack_info.get("service_name", self.container_name)
            return f"{service_name}"
        else:
            return self.container_name

class BaseStackEntity(BasePortainerEntity):
    """Base class for stack-specific entities."""

    def __init__(
        self, 
        coordinator: PortainerDataUpdateCoordinator, 
        entry_id: str, 
        stack_name: str
    ):
        """Initialize the stack entity."""
        super().__init__(coordinator, entry_id)
        self.stack_name = stack_name
        self._attr_unique_id = f"entry_{entry_id}_endpoint_{coordinator.endpoint_id}_stack_{stack_name}_{self.entity_type}"

    @property
    def entity_type(self) -> str:
        """Return the entity type for unique ID generation."""
        raise NotImplementedError

    @property
    def device_info(self) -> Dict[str, Any]:
        """Return device info."""
        return create_stack_device_info(self.entry_id, self.stack_name, self.stack_name)

    def _get_stack_data(self) -> Optional[Dict[str, Any]]:
        """Get current stack data from coordinator."""
        return self.coordinator.get_stack(self.stack_name)

    def _get_stack_containers(self) -> list:
        """Get all containers belonging to this stack."""
        return self.coordinator.get_stack_containers(self.stack_name)
