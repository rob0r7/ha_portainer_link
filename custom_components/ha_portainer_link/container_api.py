import logging
import aiohttp
from typing import List, Dict, Any, Optional

_LOGGER = logging.getLogger(__name__)

class PortainerContainerAPI:
    """Handle Portainer container operations."""

    def __init__(self, base_url: str, auth):
        """Initialize container API."""
        self.base_url = base_url
        self.auth = auth

    async def get_containers(self, endpoint_id: int) -> List[Dict[str, Any]]:
        """Get all containers for an endpoint."""
        url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/containers/json?all=1"
        try:
            async with self.auth.session.get(url, headers=self.auth.get_headers()) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    _LOGGER.error("❌ Failed to get containers: HTTP %s", resp.status)
                    return []
        except Exception as e:
            _LOGGER.exception("❌ Error getting containers: %s", e)
            return []

    async def inspect_container(self, endpoint_id: int, container_id: str) -> Optional[Dict[str, Any]]:
        """Inspect a specific container."""
        url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/containers/{container_id}/json"
        try:
            async with self.auth.session.get(url, headers=self.auth.get_headers()) as resp:
                if resp.status == 200:
                    container_data = await resp.json()
                    _LOGGER.debug("✅ Successfully inspected container %s", container_id)
                    return container_data
                else:
                    _LOGGER.error("❌ Failed to inspect container %s: HTTP %s", container_id, resp.status)
                    return None
        except Exception as e:
            _LOGGER.exception("❌ Exception inspecting container %s: %s", container_id, e)
            return None

    async def get_container_stats(self, endpoint_id: int, container_id: str) -> Optional[Dict[str, Any]]:
        """Get container statistics."""
        url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/containers/{container_id}/stats?stream=false"
        try:
            async with self.auth.session.get(url, headers=self.auth.get_headers()) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    _LOGGER.error("❌ Failed to get container stats: HTTP %s", resp.status)
                    return None
        except Exception as e:
            _LOGGER.exception("❌ Error getting container stats: %s", e)
            return None

    async def start_container(self, endpoint_id: int, container_id: str) -> bool:
        """Start a container."""
        url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/containers/{container_id}/start"
        try:
            async with self.auth.session.post(url, headers=self.auth.get_headers()) as resp:
                success = resp.status == 204
                if success:
                    _LOGGER.info("✅ Successfully started container %s", container_id)
                else:
                    _LOGGER.error("❌ Failed to start container %s: HTTP %s", container_id, resp.status)
                return success
        except Exception as e:
            _LOGGER.exception("❌ Error starting container %s: %s", container_id, e)
            return False

    async def stop_container(self, endpoint_id: int, container_id: str) -> bool:
        """Stop a container."""
        url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/containers/{container_id}/stop"
        try:
            async with self.auth.session.post(url, headers=self.auth.get_headers()) as resp:
                success = resp.status == 204
                if success:
                    _LOGGER.info("✅ Successfully stopped container %s", container_id)
                else:
                    _LOGGER.error("❌ Failed to stop container %s: HTTP %s", container_id, resp.status)
                return success
        except Exception as e:
            _LOGGER.exception("❌ Error stopping container %s: %s", container_id, e)
            return False

    async def restart_container(self, endpoint_id: int, container_id: str) -> bool:
        """Restart a container."""
        url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/containers/{container_id}/restart"
        try:
            async with self.auth.session.post(url, headers=self.auth.get_headers()) as resp:
                success = resp.status == 204
                if success:
                    _LOGGER.info("✅ Successfully restarted container %s", container_id)
                else:
                    _LOGGER.error("❌ Failed to restart container %s: HTTP %s", container_id, resp.status)
                return success
        except Exception as e:
            _LOGGER.exception("❌ Error restarting container %s: %s", container_id, e)
            return False

    def get_container_stack_info(self, container_info: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract stack information from container info."""
        try:
            if not container_info:
                _LOGGER.warning("⚠️ Container info is empty, cannot determine stack info")
                return {
                    "stack_name": None,
                    "service_name": None,
                    "container_number": None,
                    "is_stack_container": False
                }
            
            labels = container_info.get("Config", {}).get("Labels", {})
            stack_name = labels.get("com.docker.compose.project")
            stack_service = labels.get("com.docker.compose.service")
            stack_container_number = labels.get("com.docker.compose.container-number")
            
            # Log all labels for debugging
            compose_labels = {k: v for k, v in labels.items() if k.startswith("com.docker.compose")}
            if compose_labels:
                _LOGGER.debug("🔍 Found compose labels: %s", compose_labels)
            
            _LOGGER.debug("🔍 Stack detection: stack_name=%s, service=%s, number=%s", 
                         stack_name, stack_service, stack_container_number)
            
            if stack_name:
                _LOGGER.info("✅ Container is part of stack: %s (service: %s)", stack_name, stack_service)
                return {
                    "stack_name": stack_name,
                    "service_name": stack_service,
                    "container_number": stack_container_number,
                    "is_stack_container": True
                }
            else:
                _LOGGER.debug("ℹ️ Container is standalone (no stack labels found)")
                return {
                    "stack_name": None,
                    "service_name": None,
                    "container_number": None,
                    "is_stack_container": False
                }
        except Exception as e:
            _LOGGER.exception("❌ Error extracting stack info from container: %s", e)
            return {
                "stack_name": None,
                "service_name": None,
                "container_number": None,
                "is_stack_container": False
            }
