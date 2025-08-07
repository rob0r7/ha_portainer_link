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

    def __init__(self, hass: HomeAssistant, api: PortainerAPI, endpoint_id: int):
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name=f"portainer_data_{endpoint_id}",
            update_interval=timedelta(minutes=5),  # 5 minutes - good balance between responsiveness and rate limiting
        )
        self.api = api
        self.endpoint_id = endpoint_id
        self.containers: Dict[str, Dict[str, Any]] = {}
        self.stacks: Dict[str, Dict[str, Any]] = {}
        self.container_stack_map: Dict[str, str] = {}  # container_id -> stack_name
        self.container_stack_info: Dict[str, Dict[str, Any]] = {}  # container_id -> detailed stack info

    async def _async_update_data(self) -> Dict[str, Any]:
        """Update container and stack data."""
        try:
            _LOGGER.debug("🔄 Updating Portainer data for endpoint %s", self.endpoint_id)
            
            # Get containers and stacks in parallel
            containers_task = self.api.get_containers(self.endpoint_id)
            stacks_task = self.api.get_stacks(self.endpoint_id)
            
            containers, stacks = await asyncio.gather(containers_task, stacks_task)
            
            # Process containers
            self.containers = {}
            self.container_stack_map = {}
            self.container_stack_info = {}
            
            stack_containers_count = 0
            standalone_containers_count = 0
            
            # Save containers and prepare inspection tasks
            inspection_tasks: List[asyncio.Task] = []
            container_ids: List[str] = []
            for container in containers:
                container_id = container["Id"]
                container_name = container.get("Names", ["unknown"])[0].strip("/")
                self.containers[container_id] = container
                container_ids.append(container_id)
                inspection_tasks.append(asyncio.create_task(self.api.inspect_container(self.endpoint_id, container_id)))
            
            # Run inspections concurrently
            inspection_results = await asyncio.gather(*inspection_tasks, return_exceptions=True)
            for container_id, result in zip(container_ids, inspection_results):
                container_name = self.containers.get(container_id, {}).get("Names", ["unknown"])[0].strip("/")
                if isinstance(result, Exception) or result is None:
                    if isinstance(result, Exception):
                        _LOGGER.warning("⚠️ Exception inspecting container %s: %s", container_name, result)
                    else:
                        _LOGGER.warning("⚠️ Could not inspect container %s", container_name)
                    continue
                
                stack_info = self.api.get_container_stack_info(result)
                self.container_stack_info[container_id] = stack_info
                
                if stack_info.get("is_stack_container"):
                    stack_name = stack_info.get("stack_name")
                    service_name = stack_info.get("service_name")
                    if stack_name:
                        self.container_stack_map[container_id] = stack_name
                        stack_containers_count += 1
                        _LOGGER.debug("✅ Container %s is part of stack %s (service: %s)", 
                                     container_name, stack_name, service_name)
                    else:
                        _LOGGER.warning("⚠️ Container %s has stack labels but no stack name", container_name)
                else:
                    standalone_containers_count += 1
                    _LOGGER.debug("ℹ️ Container %s is standalone", container_name)
            
            # Process stacks
            self.stacks = {stack["Name"]: stack for stack in stacks}
            
            _LOGGER.info("✅ Updated data: %d containers (%d stack containers, %d standalone), %d stacks", 
                         len(self.containers), stack_containers_count, standalone_containers_count, len(self.stacks))
            
            # Log stack mapping for debugging
            if self.container_stack_map:
                _LOGGER.info("📋 Stack mapping: %s", self.container_stack_map)
            
            return {
                "containers": containers,
                "stacks": stacks,
                "container_stack_map": self.container_stack_map
            }
            
        except Exception as e:
            _LOGGER.error("❌ Failed to update Portainer data: %s", e)
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

    def get_stack_containers(self, stack_name: str) -> List[Dict[str, Any]]:
        """Get all containers belonging to a stack."""
        stack_containers = []
        for container_id, container in self.containers.items():
            if self.container_stack_map.get(container_id) == stack_name:
                stack_containers.append(container)
        return stack_containers

    def get_standalone_containers(self) -> List[Dict[str, Any]]:
        """Get all standalone containers (not part of any stack)."""
        standalone_containers = []
        for container_id, container in self.containers.items():
            if container_id not in self.container_stack_map:
                standalone_containers.append(container)
        return standalone_containers
