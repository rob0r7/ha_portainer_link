import logging
from datetime import timedelta
from typing import Dict, List, Optional, Any
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.core import HomeAssistant
import asyncio

from .portainer_api import PortainerAPI
from .const import (
    CONF_UPDATE_INTERVAL, CONF_ENABLE_UPDATE_CHECKS, CONF_ENABLE_HEALTH_MONITORING,
    CONF_ENABLE_RESOURCE_MONITORING, CONF_ENABLE_STACK_VIEW, CONF_ENABLE_CONTAINER_LOGS,
    CONF_ENABLE_RESOURCE_SENSORS, CONF_ENABLE_VERSION_SENSORS, CONF_ENABLE_UPDATE_SENSORS,
    CONF_ENABLE_STACK_BUTTONS, CONF_ENABLE_CONTAINER_BUTTONS, CONF_ENABLE_BULK_OPERATIONS,
    DEFAULT_UPDATE_INTERVAL, DEFAULT_ENABLE_UPDATE_CHECKS, DEFAULT_ENABLE_HEALTH_MONITORING,
    DEFAULT_ENABLE_RESOURCE_MONITORING, DEFAULT_ENABLE_STACK_VIEW, DEFAULT_ENABLE_CONTAINER_LOGS,
    DEFAULT_ENABLE_RESOURCE_SENSORS, DEFAULT_ENABLE_VERSION_SENSORS, DEFAULT_ENABLE_UPDATE_SENSORS,
    DEFAULT_ENABLE_STACK_BUTTONS, DEFAULT_ENABLE_CONTAINER_BUTTONS, DEFAULT_ENABLE_BULK_OPERATIONS
)

_LOGGER = logging.getLogger(__name__)

class PortainerDataUpdateCoordinator(DataUpdateCoordinator):
    """Coordinator for Portainer data updates."""

    def __init__(self, hass: HomeAssistant, api: PortainerAPI, endpoint_id: int, config: Dict[str, Any]):
        """Initialize the coordinator."""
        # Get configurable update interval
        update_interval = config.get(CONF_UPDATE_INTERVAL, DEFAULT_UPDATE_INTERVAL)
        
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

    async def _async_update_data(self) -> Dict[str, Any]:
        """Update container and stack data."""
        try:
            _LOGGER.debug("🔄 Updating Portainer data for endpoint %s", self.endpoint_id)
            
            # Get containers and stacks in parallel
            containers_task = self.api.get_containers(self.endpoint_id)
            stacks_task = self.api.get_stacks(self.endpoint_id) if self.is_stack_view_enabled() else asyncio.sleep(0)
            
            if self.is_stack_view_enabled():
                containers, stacks = await asyncio.gather(containers_task, stacks_task)
            else:
                containers = await containers_task
                stacks = []
            
            # Process containers
            self.containers = {}
            self.container_stack_map = {}
            self.container_stack_info = {}
            
            stack_containers_count = 0
            standalone_containers_count = 0
            
            for container in containers:
                container_id = container["Id"]
                container_name = container.get("Names", ["unknown"])[0].strip("/")
                self.containers[container_id] = container
                
                # Only get stack information if stack view is enabled
                if self.is_stack_view_enabled():
                    # Get stack information for each container
                    container_info = await self.api.inspect_container(self.endpoint_id, container_id)
                    if container_info:
                        stack_info = self.api.get_container_stack_info(container_info)
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
                    else:
                        _LOGGER.warning("⚠️ Could not inspect container %s", container_name)
                else:
                    # In lightweight mode, all containers are standalone
                    standalone_containers_count += 1
            
            # Process stacks only if stack view is enabled
            if self.is_stack_view_enabled():
                self.stacks = {stack["Name"]: stack for stack in stacks}
                _LOGGER.info("✅ Updated data: %d containers (%d stack containers, %d standalone), %d stacks", 
                             len(self.containers), stack_containers_count, standalone_containers_count, len(self.stacks))
            else:
                self.stacks = {}
                _LOGGER.info("✅ Updated data: %d containers (all standalone, stack view disabled)", 
                             len(self.containers))
            
            # Log stack mapping for debugging (only if stack view enabled)
            if self.is_stack_view_enabled() and self.container_stack_map:
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
        """Get all containers that belong to a specific stack."""
        stack_containers = []
        for container_id, container_stack in self.container_stack_map.items():
            if container_stack == stack_name:
                container_data = self.containers.get(container_id)
                if container_data:
                    stack_containers.append(container_data)
        return stack_containers

    def get_standalone_containers(self) -> List[Dict[str, Any]]:
        """Get all containers that are not part of any stack."""
        standalone_containers = []
        for container_id, container_data in self.containers.items():
            if container_id not in self.container_stack_map:
                standalone_containers.append(container_data)
        return standalone_containers

    # Feature toggle methods
    def is_update_checks_enabled(self) -> bool:
        """Check if update checks are enabled."""
        return self.config.get(CONF_ENABLE_UPDATE_CHECKS, DEFAULT_ENABLE_UPDATE_CHECKS)

    def is_health_monitoring_enabled(self) -> bool:
        """Check if health monitoring is enabled."""
        return self.config.get(CONF_ENABLE_HEALTH_MONITORING, DEFAULT_ENABLE_HEALTH_MONITORING)

    def is_resource_monitoring_enabled(self) -> bool:
        """Check if resource monitoring is enabled."""
        return self.config.get(CONF_ENABLE_RESOURCE_MONITORING, DEFAULT_ENABLE_RESOURCE_MONITORING)

    def is_stack_view_enabled(self) -> bool:
        """Check if stack view is enabled."""
        return self.config.get(CONF_ENABLE_STACK_VIEW, DEFAULT_ENABLE_STACK_VIEW)

    def is_container_logs_enabled(self) -> bool:
        """Check if container logs are enabled."""
        return self.config.get(CONF_ENABLE_CONTAINER_LOGS, DEFAULT_ENABLE_CONTAINER_LOGS)

    def is_resource_sensors_enabled(self) -> bool:
        """Check if resource sensors are enabled."""
        return self.config.get(CONF_ENABLE_RESOURCE_SENSORS, DEFAULT_ENABLE_RESOURCE_SENSORS)

    def is_version_sensors_enabled(self) -> bool:
        """Check if version sensors are enabled."""
        return self.config.get(CONF_ENABLE_VERSION_SENSORS, DEFAULT_ENABLE_VERSION_SENSORS)

    def is_update_sensors_enabled(self) -> bool:
        """Check if update sensors are enabled."""
        return self.config.get(CONF_ENABLE_UPDATE_SENSORS, DEFAULT_ENABLE_UPDATE_SENSORS)

    def is_stack_buttons_enabled(self) -> bool:
        """Check if stack buttons are enabled."""
        return self.config.get(CONF_ENABLE_STACK_BUTTONS, DEFAULT_ENABLE_STACK_BUTTONS)

    def is_container_buttons_enabled(self) -> bool:
        """Check if container buttons are enabled."""
        return self.config.get(CONF_ENABLE_CONTAINER_BUTTONS, DEFAULT_ENABLE_CONTAINER_BUTTONS)

    def is_bulk_operations_enabled(self) -> bool:
        """Check if bulk operations are enabled."""
        return self.config.get(CONF_ENABLE_BULK_OPERATIONS, DEFAULT_ENABLE_BULK_OPERATIONS)
