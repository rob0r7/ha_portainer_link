import logging
import aiohttp
from typing import List, Dict, Any, Optional

_LOGGER = logging.getLogger(__name__)

class PortainerStackAPI:
    """Handle Portainer stack operations."""

    def __init__(self, base_url: str, auth, ssl_verify: bool = True):
        """Initialize stack API."""
        self.base_url = base_url
        self.auth = auth
        self.ssl_verify = ssl_verify

    async def get_stacks(self, endpoint_id: int) -> List[Dict[str, Any]]:
        """Get all stacks from Portainer for a specific endpoint."""
        try:
            stacks_url = f"{self.base_url}/api/stacks"
            async with self.auth.session.get(stacks_url, headers=self.auth.get_headers(), ssl=self.ssl_verify) as resp:
                if resp.status == 200:
                    stacks_data = await resp.json()
                    # Filter stacks for the specific endpoint
                    endpoint_stacks = [stack for stack in stacks_data if stack.get("EndpointId") == endpoint_id]
                    _LOGGER.debug("Found %d stacks for endpoint %s", len(endpoint_stacks), endpoint_id)
                    return endpoint_stacks
                else:
                    _LOGGER.error("❌ Could not get stacks list: HTTP %s", resp.status)
                    return []
        except Exception as e:
            _LOGGER.exception("❌ Error getting stacks: %s", e)
            return []

    async def stop_stack(self, endpoint_id: int, stack_name: str) -> bool:
        """Stop all containers in a stack."""
        try:
            _LOGGER.info("🛑 Stopping stack %s", stack_name)
            
            # Get all containers in the stack
            containers_url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/containers/json?all=1"
            async with self.auth.session.get(containers_url, headers=self.auth.get_headers(), ssl=self.ssl_verify) as resp:
                if resp.status != 200:
                    _LOGGER.error("❌ Could not get containers list: HTTP %s", resp.status)
                    return False
                
                containers_data = await resp.json()
                stack_containers = []
                
                # Find all containers belonging to this stack
                for container in containers_data:
                    labels = container.get("Labels", {})
                    if labels.get("com.docker.compose.project") == stack_name:
                        stack_containers.append(container["Id"])
                
                if not stack_containers:
                    _LOGGER.warning("⚠️ No containers found for stack %s", stack_name)
                    return False
                
                _LOGGER.info("Found %d containers in stack %s", len(stack_containers), stack_name)
                
                # Stop each container in the stack
                success_count = 0
                for container_id in stack_containers:
                    try:
                        stop_url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/containers/{container_id}/stop"
                        async with self.auth.session.post(stop_url, headers=self.auth.get_headers(), ssl=self.ssl_verify) as stop_resp:
                            if stop_resp.status == 204:
                                success_count += 1
                                _LOGGER.debug("✅ Stopped container %s", container_id)
                            else:
                                _LOGGER.warning("⚠️ Failed to stop container %s: HTTP %s", container_id, stop_resp.status)
                    except Exception as e:
                        _LOGGER.warning("⚠️ Error stopping container %s: %s", container_id, e)
                
                _LOGGER.info("✅ Successfully stopped %d/%d containers in stack %s", 
                           success_count, len(stack_containers), stack_name)
                return success_count > 0
                
        except Exception as e:
            _LOGGER.exception("❌ Error stopping stack %s: %s", stack_name, e)
            return False

    async def start_stack(self, endpoint_id: int, stack_name: str) -> bool:
        """Start all containers in a stack."""
        try:
            _LOGGER.info("▶️ Starting stack %s", stack_name)
            
            # Get all containers in the stack
            containers_url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/containers/json?all=1"
            async with self.auth.session.get(containers_url, headers=self.auth.get_headers(), ssl=self.ssl_verify) as resp:
                if resp.status != 200:
                    _LOGGER.error("❌ Could not get containers list: HTTP %s", resp.status)
                    return False
                
                containers_data = await resp.json()
                stack_containers = []
                
                # Find all containers belonging to this stack
                for container in containers_data:
                    labels = container.get("Labels", {})
                    if labels.get("com.docker.compose.project") == stack_name:
                        stack_containers.append(container["Id"])
                
                if not stack_containers:
                    _LOGGER.warning("⚠️ No containers found for stack %s", stack_name)
                    return False
                
                _LOGGER.info("Found %d containers in stack %s", len(stack_containers), stack_name)
                
                # Start each container in the stack
                success_count = 0
                for container_id in stack_containers:
                    try:
                        start_url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/containers/{container_id}/start"
                        async with self.auth.session.post(start_url, headers=self.auth.get_headers(), ssl=self.ssl_verify) as start_resp:
                            if start_resp.status == 204:
                                success_count += 1
                                _LOGGER.debug("✅ Started container %s", container_id)
                            else:
                                _LOGGER.warning("⚠️ Failed to start container %s: HTTP %s", container_id, start_resp.status)
                    except Exception as e:
                        _LOGGER.warning("⚠️ Error starting container %s: %s", container_id, e)
                
                _LOGGER.info("✅ Successfully started %d/%d containers in stack %s", 
                           success_count, len(stack_containers), stack_name)
                return success_count > 0
                
        except Exception as e:
            _LOGGER.exception("❌ Error starting stack %s: %s", stack_name, e)
            return False

    async def update_stack(self, endpoint_id: int, stack_name: str) -> bool:
        """Force update entire stack with image pulling and redeployment."""
        try:
            _LOGGER.info("🔄 Force updating stack %s", stack_name)
            
            # Get stack information
            stacks_data = await self.get_stacks(endpoint_id)
            if not stacks_data:
                _LOGGER.error("Could not get stacks list: %s", endpoint_id)
                return False
            
            stack_id = None
            for stack in stacks_data:
                if stack.get("Name") == stack_name:
                    stack_id = stack.get("Id")
                    break
            
            if not stack_id:
                _LOGGER.error("Could not find stack %s", stack_name)
                return False
            
            # Update the stack (this will pull new images and recreate containers)
            update_url = f"{self.base_url}/api/stacks/{stack_id}/update"
            update_payload = {
                "prune": False,  # Don't remove unused images
                "pullImage": True  # Pull latest images
            }
            
            async with self.auth.session.put(update_url, headers=self.auth.get_headers(), json=update_payload, ssl=self.ssl_verify) as resp:
                if resp.status == 200:
                    _LOGGER.info("✅ Successfully updated stack %s", stack_name)
                    return True
                else:
                    _LOGGER.error("❌ Failed to update stack %s: %s", stack_name, resp.status)
                    return False
                    
        except Exception as e:
            _LOGGER.exception("❌ Error updating stack %s: %s", stack_name, e)
            return False
