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
            update_interval=timedelta(seconds=30),
        )
        self.api = api
        self.endpoint_id = endpoint_id
        self.containers: Dict[str, Dict[str, Any]] = {}
        self.stacks: Dict[str, Dict[str, Any]] = {}
        self.container_stack_map: Dict[str, str] = {}  # container_id -> stack_name

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
            
            for container in containers:
                container_id = container["Id"]
                self.containers[container_id] = container
                
                # Get stack information for each container
                container_info = await self.api.inspect_container(self.endpoint_id, container_id)
                if container_info:
                    stack_info = self.api.get_container_stack_info(container_info)
                    if stack_info.get("is_stack_container"):
                        stack_name = stack_info.get("stack_name")
                        if stack_name:
                            self.container_stack_map[container_id] = stack_name
            
            # Process stacks
            self.stacks = {stack["Name"]: stack for stack in stacks}
            
            _LOGGER.debug("✅ Updated data: %d containers, %d stacks", 
                         len(self.containers), len(self.stacks))
            
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
