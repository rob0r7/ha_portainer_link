import logging
import aiohttp
from typing import List, Dict, Any, Optional
from aiohttp.client_exceptions import ClientConnectorCertificateError

_LOGGER = logging.getLogger(__name__)

class PortainerContainerAPI:
    """Handles all container-specific API operations."""

    def __init__(self, base_url: str, auth, ssl_verify: bool = True):
        """Initialize the container API."""
        self.base_url = base_url
        self.auth = auth
        self.ssl_verify = ssl_verify

    async def get_containers(self, endpoint_id: int) -> List[Dict[str, Any]]:
        """Get all containers for an endpoint."""
        url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/containers/json?all=1"
        
        _LOGGER.info("🔍 Getting containers from URL: %s", url)
        
        # Try with current SSL setting first
        try:
            _LOGGER.debug("🔧 Container API get_containers with ssl_verify: %s", self.ssl_verify)
            async with self.auth.session.get(url, headers=self.auth.get_headers(), ssl=self.ssl_verify) as resp:
                if resp.status == 200:
                    containers = await resp.json()
                    _LOGGER.info("✅ Successfully got %d containers from endpoint %s", len(containers), endpoint_id)
                    return containers
                elif resp.status == 404:
                    _LOGGER.error("❌ Endpoint %s not found (404). This could mean:", endpoint_id)
                    _LOGGER.error("   - The endpoint ID is incorrect")
                    _LOGGER.error("   - The endpoint doesn't exist")
                    _LOGGER.error("   - You don't have access to this endpoint")
                    _LOGGER.error("   - The Portainer URL is incorrect")
                    return []
                elif resp.status == 403:
                    _LOGGER.error("❌ Access denied (403) to endpoint %s. Check your permissions.", endpoint_id)
                    return []
                else:
                    _LOGGER.error("❌ Failed to get containers: HTTP %s", resp.status)
                    return []
        except ClientConnectorCertificateError as e:
            _LOGGER.info("🔧 SSL certificate error, retrying with SSL disabled: %s", e)
            # Retry with SSL disabled
            try:
                async with self.auth.session.get(url, headers=self.auth.get_headers(), ssl=False) as resp:
                    if resp.status == 200:
                        _LOGGER.info("✅ Successfully connected with SSL disabled")
                        # Update SSL setting for future calls
                        self.ssl_verify = False
                        containers = await resp.json()
                        _LOGGER.info("✅ Successfully got %d containers from endpoint %s", len(containers), endpoint_id)
                        return containers
                    elif resp.status == 404:
                        _LOGGER.error("❌ Endpoint %s not found (404) even with SSL disabled.", endpoint_id)
                        return []
                    else:
                        _LOGGER.error("❌ Failed to get containers: HTTP %s", resp.status)
                        return []
            except Exception as retry_e:
                _LOGGER.exception("❌ Error getting containers with SSL disabled: %s", retry_e)
                return []
        except Exception as e:
            _LOGGER.exception("❌ Error getting containers: %s", e)
            return []

    async def inspect_container(self, endpoint_id: int, container_id: str) -> Optional[Dict[str, Any]]:
        """Inspect a specific container."""
        url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/containers/{container_id}/json"
        try:
            async with self.auth.session.get(url, headers=self.auth.get_headers(), ssl=self.ssl_verify) as resp:
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
            async with self.auth.session.get(url, headers=self.auth.get_headers(), ssl=self.ssl_verify) as resp:
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
            async with self.auth.session.post(url, headers=self.auth.get_headers(), ssl=self.ssl_verify) as resp:
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
            async with self.auth.session.post(url, headers=self.auth.get_headers(), ssl=self.ssl_verify) as resp:
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
            async with self.auth.session.post(url, headers=self.auth.get_headers(), ssl=self.ssl_verify) as resp:
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

            # Get labels from container info
            labels = container_info.get("Config", {}).get("Labels", {})
            
            # Log all labels for debugging
            _LOGGER.debug("🔍 Stack detection for container: labels=%s", labels)
            
            # Check for Docker Compose labels
            stack_name = labels.get("com.docker.compose.project")
            service_name = labels.get("com.docker.compose.service")
            container_number = labels.get("com.docker.compose.container-number")
            
            if stack_name and service_name:
                _LOGGER.debug("✅ Container is part of stack: %s (service: %s, container: %s)", 
                             stack_name, service_name, container_number)
                return {
                    "stack_name": stack_name,
                    "service_name": service_name,
                    "container_number": container_number,
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
            _LOGGER.exception("❌ Error extracting stack info: %s", e)
            return {
                "stack_name": None,
                "service_name": None,
                "container_number": None,
                "is_stack_container": False
            }

    async def get_available_endpoints(self) -> List[Dict[str, Any]]:
        """Get all available endpoints to help debug 404 errors."""
        url = f"{self.base_url}/api/endpoints"
        
        try:
            _LOGGER.info("🔍 Getting available endpoints from: %s", url)
            
            # Try with current SSL setting first
            try:
                async with self.auth.session.get(url, headers=self.auth.get_headers(), ssl=self.ssl_verify) as resp:
                    if resp.status == 200:
                        endpoints = await resp.json()
                        _LOGGER.info("✅ Found %d available endpoints:", len(endpoints))
                        for endpoint in endpoints:
                            endpoint_id = endpoint.get("Id")
                            endpoint_name = endpoint.get("Name", "Unknown")
                            endpoint_type = endpoint.get("Type", "Unknown")
                            _LOGGER.info("   - ID: %s, Name: %s, Type: %s", endpoint_id, endpoint_name, endpoint_type)
                        return endpoints
                    else:
                        _LOGGER.error("❌ Failed to get endpoints: HTTP %s", resp.status)
                        return []
            except ClientConnectorCertificateError as e:
                _LOGGER.info("🔧 SSL certificate error, retrying with SSL disabled: %s", e)
                # Retry with SSL disabled
                try:
                    async with self.auth.session.get(url, headers=self.auth.get_headers(), ssl=False) as resp:
                        if resp.status == 200:
                            _LOGGER.info("✅ Successfully connected with SSL disabled")
                            # Update SSL setting for future calls
                            self.ssl_verify = False
                            endpoints = await resp.json()
                            _LOGGER.info("✅ Found %d available endpoints:", len(endpoints))
                            for endpoint in endpoints:
                                endpoint_id = endpoint.get("Id")
                                endpoint_name = endpoint.get("Name", "Unknown")
                                endpoint_type = endpoint.get("Type", "Unknown")
                                _LOGGER.info("   - ID: %s, Name: %s, Type: %s", endpoint_id, endpoint_name, endpoint_type)
                            return endpoints
                        else:
                            _LOGGER.error("❌ Failed to get endpoints: HTTP %s", resp.status)
                            return []
                except Exception as retry_e:
                    _LOGGER.exception("❌ Error getting endpoints with SSL disabled: %s", retry_e)
                    return []
                    
        except Exception as e:
            _LOGGER.exception("❌ Error getting endpoints: %s", e)
            return []

    async def check_endpoint_exists(self, endpoint_id: int) -> bool:
        """Check if a specific endpoint exists."""
        url = f"{self.base_url}/api/endpoints/{endpoint_id}"
        
        try:
            _LOGGER.info("🔍 Checking if endpoint %s exists: %s", endpoint_id, url)
            
            # Try with current SSL setting first
            try:
                async with self.auth.session.get(url, headers=self.auth.get_headers(), ssl=self.ssl_verify) as resp:
                    if resp.status == 200:
                        endpoint_data = await resp.json()
                        endpoint_name = endpoint_data.get("Name", "Unknown")
                        _LOGGER.info("✅ Endpoint %s exists: %s", endpoint_id, endpoint_name)
                        return True
                    elif resp.status == 404:
                        _LOGGER.error("❌ Endpoint %s does not exist (404)", endpoint_id)
                        return False
                    else:
                        _LOGGER.error("❌ Failed to check endpoint %s: HTTP %s", endpoint_id, resp.status)
                        return False
            except ClientConnectorCertificateError as e:
                _LOGGER.info("🔧 SSL certificate error, retrying with SSL disabled: %s", e)
                # Retry with SSL disabled
                try:
                    async with self.auth.session.get(url, headers=self.auth.get_headers(), ssl=False) as resp:
                        if resp.status == 200:
                            _LOGGER.info("✅ Successfully connected with SSL disabled")
                            # Update SSL setting for future calls
                            self.ssl_verify = False
                            endpoint_data = await resp.json()
                            endpoint_name = endpoint_data.get("Name", "Unknown")
                            _LOGGER.info("✅ Endpoint %s exists: %s", endpoint_id, endpoint_name)
                            return True
                        elif resp.status == 404:
                            _LOGGER.error("❌ Endpoint %s does not exist (404) even with SSL disabled", endpoint_id)
                            return False
                        else:
                            _LOGGER.error("❌ Failed to check endpoint %s: HTTP %s", endpoint_id, resp.status)
                            return False
                except Exception as retry_e:
                    _LOGGER.exception("❌ Error checking endpoint with SSL disabled: %s", retry_e)
                    return False
                    
        except Exception as e:
            _LOGGER.exception("❌ Error checking endpoint %s: %s", endpoint_id, e)
            return False
