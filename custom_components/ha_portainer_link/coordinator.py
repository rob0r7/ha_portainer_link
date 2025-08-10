import logging
from datetime import timedelta
from typing import Dict, List, Optional, Any
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.core import HomeAssistant
import asyncio

from .portainer_api import PortainerAPI

_LOGGER = logging.getLogger(__name__)

class PortainerDataUpdateCoordinator(DataUpdateCoordinator):
    """Coordinator for Portainer data updates."""

    def __init__(self, hass: HomeAssistant, api: PortainerAPI, endpoint_id: int, config: Dict[str, Any]):
        """Initialize the coordinator."""
        # Get update interval from config
        update_interval = config.get("update_interval", 5)
        
        super().__init__(
            hass,
            _LOGGER,
            name=f"portainer_data_{endpoint_id}",
            update_interval=timedelta(minutes=update_interval),
        )
        self.api = api
        self.endpoint_id = endpoint_id
        self.config = config
        self.containers: Dict[str, Dict[str, Any]] = {}
        self.stacks: Dict[str, Dict[str, Any]] = {}
        self.container_stack_map: Dict[str, str] = {}  # container_id -> stack_name
        self.container_stack_info: Dict[str, Dict[str, Any]] = {}  # container_id -> detailed stack info
        self.update_availability: Dict[str, bool] = {}  # container_id -> has_updates
        self.stable_container_map: Dict[str, str] = {}  # stable_id -> container_id

    async def _async_update_data(self) -> Dict[str, Any]:
        """Update container and stack data."""
        try:
            _LOGGER.debug("🔄 Updating Portainer data for endpoint %s", self.endpoint_id)
            
            # First, check if the endpoint exists
            endpoint_exists = await self.api.containers.check_endpoint_exists(self.endpoint_id)
            if not endpoint_exists:
                _LOGGER.error("❌ Endpoint %s does not exist. Getting available endpoints...", self.endpoint_id)
                available_endpoints = await self.api.containers.get_available_endpoints()
                if available_endpoints:
                    _LOGGER.error("❌ Available endpoints are: %s", [ep.get("Id") for ep in available_endpoints])
                else:
                    _LOGGER.error("❌ No endpoints found. Check your Portainer configuration.")
                return {
                    "containers": [],
                    "stacks": [],
                    "container_stack_map": {}
                }
            
            # Get containers and stacks in parallel
            containers_task = self.api.get_containers(self.endpoint_id)
            stacks_task = self.api.get_stacks(self.endpoint_id) if self.is_stack_view_enabled() else asyncio.sleep(0, result=[])
            
            if self.is_stack_view_enabled():
                containers, stacks = await asyncio.gather(containers_task, stacks_task)
            else:
                containers = await containers_task
                stacks = []
            
            # Process containers
            self.containers = {}
            self.container_stack_map = {}
            self.container_stack_info = {}
            self.stable_container_map = {}  # Reset stable container map
            
            stack_containers_count = 0
            standalone_containers_count = 0
            
            for container in containers:
                container_id = container["Id"]
                container_name = container.get("Names", ["unknown"])[0].strip("/")
                container_state = container.get("State", {})
                
                # Handle both string and dictionary state formats
                if isinstance(container_state, dict):
                    is_running = container_state.get("Running", False)
                elif isinstance(container_state, str):
                    is_running = container_state.lower() == "running"
                else:
                    is_running = False
                
                _LOGGER.debug("🔍 Processing container: %s (ID: %s, Running: %s, State: %s)", 
                             container_name, container_id, is_running, container_state)
                
                self.containers[container_id] = container
                
                # Only get stack information if stack view is enabled
                if self.is_stack_view_enabled():
                    # Extract stack information from container labels (much faster than individual inspection)
                    labels = container.get("Labels", {}) or {}
                    stack_name = labels.get("com.docker.compose.project")
                    service_name = labels.get("com.docker.compose.service")
                    container_number = labels.get("com.docker.compose.container-number")
                    
                    if stack_name:
                        # This is a stack container
                        stack_info = {
                            "stack_name": stack_name,
                            "service_name": service_name,
                            "container_number": container_number,
                            "is_stack_container": True
                        }
                        self.container_stack_info[container_id] = stack_info
                        self.container_stack_map[container_id] = stack_name
                        stack_containers_count += 1
                        _LOGGER.debug("📦 Container %s belongs to stack %s", container_name, stack_name)
                    else:
                        # This is a standalone container
                        stack_info = {
                            "stack_name": None,
                            "service_name": None,
                            "container_number": None,
                            "is_stack_container": False
                        }
                        self.container_stack_info[container_id] = stack_info
                        standalone_containers_count += 1
                        _LOGGER.debug("🏠 Container %s is standalone", container_name)
                else:
                    # In lightweight mode, all containers are standalone
                    standalone_containers_count += 1
                
                # Build stable container map
                stack_info = self.container_stack_info.get(container_id, {
                    "stack_name": None,
                    "service_name": None,
                    "container_number": None,
                    "is_stack_container": False
                })
                
                # Generate stable ID
                if stack_info.get("is_stack_container"):
                    stack_name = stack_info.get("stack_name", "unknown")
                    service_name = stack_info.get("service_name", container_name)
                    stable_id = f"{stack_name}_{service_name}"
                else:
                    stable_id = container_name
                
                self.stable_container_map[stable_id] = container_id
            
            # Process stacks
            self.stacks = {}
            for stack in stacks:
                stack_name = stack.get("Name")
                if stack_name:
                    self.stacks[stack_name] = stack
            
            # Check for updates if update sensors are enabled (but don't block initial load)
            if self.is_update_sensors_enabled():
                # Only check updates every 5 minutes to avoid performance issues
                import time
                current_time = time.time()
                last_update_check = getattr(self, '_last_update_check', 0)
                
                if current_time - last_update_check > 300:  # 5 minutes
                    _LOGGER.debug("🔍 Checking for container updates...")
                    self.update_availability = {}
                    # Check updates for each container (this could be optimized further)
                    for container_id in self.containers:
                        try:
                            has_updates = await self.api.images.check_image_updates(self.endpoint_id, container_id)
                            self.update_availability[container_id] = has_updates
                        except Exception as e:
                            _LOGGER.debug("⚠️ Could not check updates for container %s: %s", container_id, e)
                            self.update_availability[container_id] = False
                    self._last_update_check = current_time
                else:
                    # Keep existing update availability data
                    if not hasattr(self, 'update_availability'):
                        self.update_availability = {}
            else:
                self.update_availability = {}
            
            _LOGGER.info("✅ Updated Portainer data: %d containers (%d stack, %d standalone), %d stacks", 
                        len(self.containers), stack_containers_count, standalone_containers_count, len(self.stacks))
            
            return {
                "containers": self.containers,
                "stacks": self.stacks,
                "container_stack_map": self.container_stack_map
            }
            
        except Exception as e:
            _LOGGER.exception("❌ Error updating Portainer data: %s", e)
            raise UpdateFailed(f"Failed to update Portainer data: {e}")

    def get_container(self, container_id: str) -> Optional[Dict[str, Any]]:
        """Get container data by ID."""
        return self.containers.get(container_id)

    def get_stack(self, stack_name: str) -> Optional[Dict[str, Any]]:
        """Get stack data by name."""
        return self.stacks.get(stack_name)

    def get_container_stack(self, container_id: str) -> Optional[str]:
        """Get stack name for a container."""
        return self.container_stack_map.get(container_id)

    def get_container_stack_info(self, container_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed stack information for a container."""
        return self.container_stack_info.get(container_id)

    def get_update_availability(self, container_id: str) -> bool:
        """Get update availability for a container."""
        return self.update_availability.get(container_id, False)

    def get_container_by_stable_id(self, stable_id: str) -> Optional[str]:
        """Get current container ID for a stable ID."""
        return self.stable_container_map.get(stable_id)

    def get_stack_containers(self, stack_name: str) -> List[Dict[str, Any]]:
        """Get all containers belonging to a stack."""
        stack_containers = []
        for container_id, container_data in self.containers.items():
            if self.container_stack_map.get(container_id) == stack_name:
                stack_containers.append(container_data)
        return stack_containers

    def get_standalone_containers(self) -> List[Dict[str, Any]]:
        """Get all standalone containers (not part of any stack)."""
        standalone_containers = []
        for container_id, container_data in self.containers.items():
            if container_id not in self.container_stack_map:
                standalone_containers.append(container_data)
        return standalone_containers

    # Feature toggle methods based on integration mode
    def is_stack_view_enabled(self) -> bool:
        """Check if stack view is enabled."""
        return self.config.get("enable_stack_view", False)

    def is_resource_sensors_enabled(self) -> bool:
        """Check if resource sensors are enabled."""
        return self.config.get("enable_resource_sensors", False)

    def is_version_sensors_enabled(self) -> bool:
        """Check if version sensors are enabled."""
        return self.config.get("enable_version_sensors", False)

    def is_update_sensors_enabled(self) -> bool:
        """Check if update sensors are enabled."""
        return self.config.get("enable_update_sensors", False)

    def is_stack_buttons_enabled(self) -> bool:
        """Check if stack buttons are enabled."""
        return self.config.get("enable_stack_buttons", False)

    def is_container_buttons_enabled(self) -> bool:
        """Check if container buttons are enabled."""
        return self.config.get("enable_container_buttons", True)  # Always enabled by default

    async def async_shutdown(self):
        """Shutdown the coordinator."""
        if hasattr(self.api, 'close'):
            await self.api.close()
