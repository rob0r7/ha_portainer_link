import logging
import aiohttp
from typing import List, Dict, Any, Optional

_LOGGER = logging.getLogger(__name__)

class PortainerStackAPI:
    """Handle Portainer stack operations."""

    def __init__(self, base_url: str, auth):
        """Initialize stack API."""
        self.base_url = base_url
        self.auth = auth

    async def get_stacks(self, endpoint_id: int) -> List[Dict[str, Any]]:
        """Get all stacks from Portainer for a specific endpoint."""
        try:
            stacks_url = f"{self.base_url}/api/stacks"
            async with self.auth.session.get(stacks_url, headers=self.auth.get_headers()) as resp:
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
            async with self.auth.session.get(containers_url, headers=self.auth.get_headers()) as resp:
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
                        async with self.auth.session.post(stop_url, headers=self.auth.get_headers()) as stop_resp:
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
            async with self.auth.session.get(containers_url, headers=self.auth.get_headers()) as resp:
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
                        async with self.auth.session.post(start_url, headers=self.auth.get_headers()) as start_resp:
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
            _LOGGER.info("🔄 Force updating stack %s with image pulling and redeployment", stack_name)
            _LOGGER.info("🔍 Using endpoint ID: %s", endpoint_id)
            
            # Get stack information using the corrected method
            stacks_data = await self.get_stacks(endpoint_id)
            if not stacks_data:
                _LOGGER.error("❌ Could not get stacks list for endpoint %s", endpoint_id)
                return False
            
            _LOGGER.info("🔍 Found %d stacks in Portainer for endpoint %s", len(stacks_data), endpoint_id)
            for stack in stacks_data:
                _LOGGER.info("🔍 Stack: %s (ID: %s, EndpointID: %s)", 
                           stack.get("Name"), stack.get("Id"), stack.get("EndpointId"))
            
            stack_id = None
            stack_info = None
            _LOGGER.info("🔍 Searching for stack: '%s'", stack_name)
            for stack in stacks_data:
                stack_name_from_api = stack.get("Name")
                stack_endpoint_id = stack.get("EndpointId")
                _LOGGER.debug("🔍 Comparing: '%s' with '%s' (EndpointID: %s)", 
                            stack_name, stack_name_from_api, stack_endpoint_id)
                if stack_name_from_api == stack_name and stack_endpoint_id == endpoint_id:
                    stack_id = stack.get("Id")
                    stack_info = stack
                    _LOGGER.info("✅ Found matching stack: %s (ID: %s, EndpointID: %s)", 
                               stack_name, stack_id, stack_endpoint_id)
                    break
            
            if not stack_id:
                _LOGGER.error("❌ Could not find stack '%s' in available stacks for endpoint %s", 
                            stack_name, endpoint_id)
                _LOGGER.error("❌ Available stacks: %s", 
                            [(s.get("Name"), s.get("EndpointId")) for s in stacks_data])
                return False
            
            _LOGGER.info("✅ Found stack %s with ID %s for endpoint %s", stack_name, stack_id, endpoint_id)
            
            # Get the stack file content for the update
            stack_file_url = f"{self.base_url}/api/stacks/{stack_id}/file"
            _LOGGER.info("📄 Retrieving stack file from: %s", stack_file_url)
            
            async with self.auth.session.get(stack_file_url, headers=self.auth.get_headers()) as resp:
                _LOGGER.info("📄 Stack file response status: %s", resp.status)
                if resp.status != 200:
                    response_text = await resp.text()
                    _LOGGER.error("❌ Could not get stack file for %s: HTTP %s - %s", 
                                stack_name, resp.status, response_text)
                    return False
                
                try:
                    stack_file_data = await resp.json()
                    stack_file_content = stack_file_data.get("StackFileContent", "")
                    
                    if not stack_file_content:
                        _LOGGER.error("❌ No stack file content found for %s", stack_name)
                        return False
                    
                    _LOGGER.info("✅ Retrieved stack file content for %s (%d characters)", 
                               stack_name, len(stack_file_content))
                    _LOGGER.debug("📄 Stack file content preview: %s", stack_file_content[:200] + "..." if len(stack_file_content) > 200 else stack_file_content)
                    
                except Exception as e:
                    _LOGGER.error("❌ Failed to parse stack file response for %s: %s", stack_name, e)
                    return False
            
            # Try to get stack details with environment variables
            stack_details_url = f"{self.base_url}/api/stacks/{stack_id}"
            _LOGGER.info("📋 Retrieving stack details from: %s", stack_details_url)
            
            env_variables = []
            try:
                async with self.auth.session.get(stack_details_url, headers=self.auth.get_headers()) as details_resp:
                    if details_resp.status == 200:
                        stack_details = await details_resp.json()
                        if "Env" in stack_details:
                            env_variables = stack_details.get("Env", [])
                            _LOGGER.info("📋 Found %d environment variables for stack %s", len(env_variables), stack_name)
                            for env_var in env_variables:
                                _LOGGER.debug("📋 Env: %s = %s", env_var.get("name", "unknown"), env_var.get("value", "unknown"))
                        else:
                            _LOGGER.info("📋 No environment variables found in stack details for %s", stack_name)
                    else:
                        _LOGGER.warning("⚠️ Could not get stack details: HTTP %s", details_resp.status)
            except Exception as e:
                _LOGGER.warning("⚠️ Error getting stack details: %s", e)
            
            # If no environment variables found, use defaults
            if not env_variables:
                _LOGGER.info("📋 Using default environment variables for stack %s", stack_name)
                env_variables = [
                    {"name": "UID", "value": "1000"},
                    {"name": "GID", "value": "1000"}
                ]
                _LOGGER.info("📋 Default environment variables: UID=1000, GID=1000")
            
            # Update the stack with force pull and redeployment
            update_url = f"{self.base_url}/api/stacks/{stack_id}?endpointId={endpoint_id}&type=2"
            update_payload = {
                "StackFileContent": stack_file_content,
                "Env": env_variables,
                "Prune": False,  # Don't remove unused images
                "PullImage": True  # Force pull latest images
            }
            
            _LOGGER.info("🔄 Sending stack update request to: %s", update_url)
            _LOGGER.info("🔄 Update payload keys: %s", list(update_payload.keys()))
            _LOGGER.info("🔄 StackFileContent length: %d characters", len(update_payload.get("StackFileContent", "")))
            _LOGGER.info("🔄 Environment variables count: %d", len(update_payload.get("Env", [])))
            _LOGGER.debug("🔄 Full update payload: %s", update_payload)
            
            async with self.auth.session.put(update_url, headers=self.auth.get_headers(), json=update_payload) as resp:
                _LOGGER.info("🔄 Update response status: %s", resp.status)
                
                if resp.status == 200:
                    _LOGGER.info("✅ Successfully force updated stack %s", stack_name)
                    return True
                elif resp.status == 400:
                    response_text = await resp.text()
                    _LOGGER.error("❌ Bad request for stack update %s: HTTP %s - %s", 
                                stack_name, resp.status, response_text)
                    return False
                elif resp.status == 404:
                    response_text = await resp.text()
                    _LOGGER.error("❌ Stack %s not found for update: HTTP %s - %s", 
                                stack_name, resp.status, response_text)
                    return False
                elif resp.status == 500:
                    response_text = await resp.text()
                    _LOGGER.error("❌ Server error updating stack %s: HTTP %s - %s", 
                                stack_name, resp.status, response_text)
                    return False
                else:
                    response_text = await resp.text()
                    _LOGGER.error("❌ Failed to force update stack %s: HTTP %s - %s", 
                                stack_name, resp.status, response_text)
                    return False
                    
        except Exception as e:
            _LOGGER.exception("❌ Error force updating stack %s: %s", stack_name, e)
            return False
