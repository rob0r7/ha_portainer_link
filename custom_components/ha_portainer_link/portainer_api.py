import logging
import aiohttp
from typing import Optional, Dict, Any

from .auth import PortainerAuth
from .container_api import PortainerContainerAPI
from .stack_api import PortainerStackAPI
from .image_api import PortainerImageAPI
from aiohttp import ClientConnectorCertificateError

_LOGGER = logging.getLogger(__name__)

class PortainerAPI:
    """Main Portainer API class that coordinates all operations."""

    def __init__(self, host: str, username: Optional[str] = None, 
                 password: Optional[str] = None, api_key: Optional[str] = None,
                 config: Optional[Dict[str, Any]] = None):
        """Initialize the Portainer API."""
        # Ensure host has proper scheme and format
        if not host.startswith(("http://", "https://")):
            # If no scheme provided, default to https
            host = f"https://{host}"
        
        self.base_url = host.rstrip("/")
        self.session: Optional[aiohttp.ClientSession] = None
        self._session_managed_by_ha = False
        self.ssl_verify = True  # Will be determined automatically
        self.config = config or {}
        
        # Get configured endpoint ID, default to 1 if not specified
        self.endpoint_id = self.config.get('endpoint_id', 1)
        
        _LOGGER.debug("🔧 Initializing Portainer API with base URL: %s and endpoint ID: %s", self.base_url, self.endpoint_id)
        
        # Initialize authentication
        self.auth = PortainerAuth(self.base_url, username, password, api_key, self.ssl_verify)
        
        # Initialize API modules with the base URL
        self.containers = PortainerContainerAPI(self.base_url, self.auth, self.ssl_verify, None)  # Session will be set later
        self.stacks = PortainerStackAPI(self.base_url, self.auth, self.ssl_verify, None)  # Session will be set later
        self.images = PortainerImageAPI(self.base_url, self.auth, self.config, self.ssl_verify, None)  # Session will be set later

    def set_session(self, session: aiohttp.ClientSession, *, managed_by_ha: bool = True) -> None:
        """Inject an aiohttp session (ideally from Home Assistant)."""
        self.session = session
        self._session_managed_by_ha = managed_by_ha
        # Share session with sub-clients
        self.containers.session = session
        self.stacks.session = session
        self.images.session = session

    async def initialize(self) -> bool:
        """Initialize the API connection using the provided session."""
        try:
            if self.session is None:
                _LOGGER.error("❌ Session not set. Call set_session() with HA session before initialize().")
                return False

            # Try different SSL verification approaches automatically using per-request ssl flag
            ssl_options = [
                (True, "SSL verification enabled"),
                (False, "SSL verification disabled"),
                (None, "SSL verification default")
            ]
            
            for ssl_verify, description in ssl_options:
                try:
                    _LOGGER.info("🔧 Trying connection with %s", description)
                    
                    # Update SSL verification setting for all components
                    self.ssl_verify = ssl_verify
                    self.containers.ssl_verify = ssl_verify
                    self.stacks.ssl_verify = ssl_verify
                    self.images.ssl_verify = ssl_verify
                    self.auth.ssl_verify = ssl_verify
                    
                    # Initialize authentication
                    if await self.auth.initialize(self.session):
                        # Test the connection by checking if endpoint exists first
                        if await self.containers.check_endpoint_exists(self.endpoint_id):
                            # Test the connection by trying to get containers
                            test_containers = await self.containers.get_containers(self.endpoint_id)
                            if test_containers is not None:
                                _LOGGER.info("✅ Connection successful with %s", description)
                                return True
                            else:
                                _LOGGER.warning("⚠️ Connection test failed with %s", description)
                        else:
                            _LOGGER.warning("⚠️ Endpoint %s does not exist with %s", self.endpoint_id, description)
                    else:
                        _LOGGER.warning("⚠️ Authentication failed with %s", description)
                        
                except ClientConnectorCertificateError as e:
                    _LOGGER.info("🔧 SSL certificate error with %s, trying next option: %s", description, e)
                    continue
                except Exception as e:
                    _LOGGER.debug("❌ Connection failed with %s: %s", description, e)
                    continue
            
            _LOGGER.error("❌ All SSL verification approaches failed")
            return False
            
        except Exception as e:
            _LOGGER.exception("❌ Failed to initialize Portainer API: %s", e)
            return False

    async def close(self) -> None:
        """No-op when using HA-managed session to avoid closing shared session."""
        # Do not close HA-managed sessions
        if self.session and not self._session_managed_by_ha:
            await self.session.close()
        self.session = None

    # Container operations - delegate to container API
    async def get_containers(self, endpoint_id: int):
        """Get all containers for an endpoint."""
        _LOGGER.debug("🔧 get_containers called with ssl_verify: %s", self.ssl_verify)
        return await self.containers.get_containers(endpoint_id)

    async def inspect_container(self, endpoint_id: int, container_id: str):
        """Inspect a specific container."""
        return await self.containers.inspect_container(endpoint_id, container_id)

    async def get_container_stats(self, endpoint_id: int, container_id: str):
        """Get container statistics."""
        return await self.containers.get_container_stats(endpoint_id, container_id)

    async def start_container(self, endpoint_id: int, container_id: str):
        """Start a container."""
        return await self.containers.start_container(endpoint_id, container_id)

    async def stop_container(self, endpoint_id: int, container_id: str):
        """Stop a container."""
        return await self.containers.stop_container(endpoint_id, container_id)

    async def restart_container(self, endpoint_id: int, container_id: str):
        """Restart a container."""
        return await self.containers.restart_container(endpoint_id, container_id)

    def get_container_stack_info(self, container_info: Optional[Dict[str, Any]]):
        """Extract stack information from container info."""
        return self.containers.get_container_stack_info(container_info)

    # Stack operations - delegate to stack API
    async def get_stacks(self, endpoint_id: int):
        """Get all stacks from Portainer for a specific endpoint."""
        _LOGGER.debug("🔧 get_stacks called with ssl_verify: %s", self.ssl_verify)
        return await self.stacks.get_stacks(endpoint_id)

    async def stop_stack(self, endpoint_id: int, stack_name: str):
        """Stop all containers in a stack."""
        return await self.stacks.stop_stack(endpoint_id, stack_name)

    async def start_stack(self, endpoint_id: int, stack_name: str):
        """Start all containers in a stack."""
        return await self.stacks.start_stack(endpoint_id, stack_name)

    async def update_stack(self, endpoint_id: int, stack_name: str):
        """Force update entire stack with image pulling and redeployment."""
        return await self.stacks.update_stack(endpoint_id, stack_name)

    # Image operations - delegate to image API
    async def check_image_updates(self, endpoint_id: int, container_id: str):
        """Check if updates are available for a container."""
        return await self.images.check_image_updates(endpoint_id, container_id)

    async def pull_image_update(self, endpoint_id: int, container_id: str):
        """Pull the latest image update for a container."""
        return await self.images.pull_image_update(endpoint_id, container_id)

    async def get_image_info(self, endpoint_id: int, image_id: str):
        """Get detailed information about an image."""
        return await self.images.get_image_info(endpoint_id, image_id)

    def extract_version_from_image(self, image_data: Dict[str, Any]):
        """Extract version information from image data."""
        return self.images.extract_version_from_image(image_data)

    async def get_available_version(self, endpoint_id: int, image_name: str):
        """Get available version for an image."""
        return await self.images.get_available_version(endpoint_id, image_name)

    async def get_current_digest(self, endpoint_id: int, container_id: str):
        """Get current image digest for a container."""
        return await self.images.get_current_digest(endpoint_id, container_id)

    async def get_available_digest(self, endpoint_id: int, container_id: str):
        """Get available image digest from registry for a container."""
        return await self.images.get_available_digest(endpoint_id, container_id)

    # Legacy methods for backward compatibility
    async def get_container_info(self, endpoint_id: int, container_id: str):
        """Get container information (legacy method)."""
        return await self.inspect_container(endpoint_id, container_id)

    async def get_container_image_name(self, endpoint_id: int, container_id: str):
        """Get container image name (legacy method)."""
        container_info = await self.inspect_container(endpoint_id, container_id)
        if container_info and "Config" in container_info:
            return container_info["Config"].get("Image", "")
        return ""

    # Advanced container operations
    async def recreate_container_with_new_image(self, endpoint_id: int, container_id: str):
        """Recreate a container with the latest image."""
        try:
            # Get current container info
            container_info = await self.inspect_container(endpoint_id, container_id)
            if not container_info:
                _LOGGER.error("❌ Could not get container info for %s", container_id)
                return False

            # Stop the container
            if not await self.stop_container(endpoint_id, container_id):
                _LOGGER.error("❌ Failed to stop container %s", container_id)
                return False

            # Remove the container
            remove_url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/containers/{container_id}?force=1"
            try:
                async with self.session.delete(remove_url, headers=self.auth.get_headers(), ssl=self.ssl_verify) as resp:
                    if resp.status != 204:
                        _LOGGER.error("❌ Failed to remove container %s: HTTP %s", container_id, resp.status)
                        return False
            except Exception as e:
                _LOGGER.error("❌ Error removing container %s: %s", container_id, e)
                return False

            # Create new container with same configuration but updated image
            create_url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/containers/create"
            
            # Use defensive programming to avoid KeyError
            config = container_info.get("Config", {})
            host_config = container_info.get("HostConfig", {})
            
            # Prepare container configuration with safe defaults
            container_config = {
                "Image": config.get("Image"),
                "Cmd": config.get("Cmd"),
                "Env": config.get("Env", []),
                "ExposedPorts": config.get("ExposedPorts", {}),
                "Volumes": config.get("Volumes", {}),
                "WorkingDir": config.get("WorkingDir"),
                "Entrypoint": config.get("Entrypoint"),
                "Labels": config.get("Labels", {}),
                "HostConfig": {
                    "Binds": host_config.get("Binds", []),
                    "PortBindings": host_config.get("PortBindings", {}),
                    "RestartPolicy": host_config.get("RestartPolicy", {}),
                    "NetworkMode": host_config.get("NetworkMode", "default"),
                    "CapAdd": host_config.get("CapAdd", []),
                    "CapDrop": host_config.get("CapDrop", []),
                    "SecurityOpt": host_config.get("SecurityOpt", []),
                    "Devices": host_config.get("Devices", []),
                    "ExtraHosts": host_config.get("ExtraHosts", []),
                    "VolumesFrom": host_config.get("VolumesFrom", []),
                    "CpuShares": host_config.get("CpuShares"),
                    "Memory": host_config.get("Memory"),
                    "CgroupParent": host_config.get("CgroupParent"),
                    "BlkioWeight": host_config.get("BlkioWeight"),
                    "BlkioWeightDevice": host_config.get("BlkioWeightDevice", []),
                    "BlkioDeviceReadBps": host_config.get("BlkioDeviceReadBps", []),
                    "BlkioDeviceWriteBps": host_config.get("BlkioDeviceWriteBps", []),
                    "BlkioDeviceReadIOps": host_config.get("BlkioDeviceReadIOps", []),
                    "BlkioDeviceWriteIOps": host_config.get("BlkioDeviceWriteIOps", []),
                    "CpuPeriod": host_config.get("CpuPeriod"),
                    "CpuQuota": host_config.get("CpuQuota"),
                    "CpuRealtimePeriod": host_config.get("CpuRealtimePeriod"),
                    "CpuRealtimeRuntime": host_config.get("CpuRealtimeRuntime"),
                    "CpusetCpus": host_config.get("CpusetCpus"),
                    "CpusetMems": host_config.get("CpusetMems"),
                    "DeviceCgroupRules": host_config.get("DeviceCgroupRules", []),
                    "DeviceRequests": host_config.get("DeviceRequests", []),
                    "KernelMemory": host_config.get("KernelMemory"),
                    "KernelMemoryTCP": host_config.get("KernelMemoryTCP"),
                    "MemoryReservation": host_config.get("MemoryReservation"),
                    "MemorySwap": host_config.get("MemorySwap"),
                    "MemorySwappiness": host_config.get("MemorySwappiness"),
                    "NanoCpus": host_config.get("NanoCpus"),
                    "OomKillDisable": host_config.get("OomKillDisable"),
                    "PidsLimit": host_config.get("PidsLimit"),
                    "Ulimits": host_config.get("Ulimits", []),
                    "CpuCount": host_config.get("CpuCount"),
                    "CpuPercent": host_config.get("CpuPercent"),
                    "IOMaximumIOps": host_config.get("IOMaximumIOps"),
                    "IOMaximumBandwidth": host_config.get("IOMaximumBandwidth"),
                }
            }

            # Create new container
            try:
                session = self.session or self.auth.session
                async with session.post(create_url, json=container_config, headers=self.auth.get_headers(), ssl=self.ssl_verify) as resp:
                    if resp.status == 201:
                        create_response = await resp.json()
                        new_container_id = create_response["Id"]
                        
                        # Start the new container
                        if await self.start_container(endpoint_id, new_container_id):
                            _LOGGER.info("✅ Successfully recreated container %s with new image", container_id)
                            return True
                        else:
                            _LOGGER.error("❌ Failed to start recreated container %s", container_id)
                            return False
                    else:
                        _LOGGER.error("❌ Failed to create new container: HTTP %s", resp.status)
                        return False
            except Exception as e:
                _LOGGER.error("❌ Error creating new container: %s", e)
                return False

        except Exception as e:
            _LOGGER.exception("❌ Error recreating container %s: %s", container_id, e)
            return False

    async def _update_stack_container(self, endpoint_id: int, container_id: str, stack_name: str):
        """Update a container that belongs to a stack."""
        try:
            # Get stack information
            stack_info = await self.get_container_stack_info(await self.inspect_container(endpoint_id, container_id))
            service_name = stack_info.get("service_name")
            
            if not service_name:
                _LOGGER.error("❌ Could not determine service name for container %s", container_id)
                return False

            # Update the stack service
            update_url = f"{self.base_url}/api/stacks/{stack_name}/services/{service_name}/update"
            
            # Get current service configuration
            service_url = f"{self.base_url}/api/stacks/{stack_name}/services/{service_name}"
            try:
                session = self.session or self.auth.session
                async with session.get(service_url, headers=self.auth.get_headers(), ssl=self.ssl_verify) as resp:
                    if resp.status == 200:
                        service_config = await resp.json()
                        
                        # Update the service with new image
                        update_data = {
                            "Image": service_config["Image"],
                            "UpdateConfig": {
                                "Parallelism": 1,
                                "Delay": "10s",
                                "FailureAction": "rollback",
                                "Monitor": "5s",
                                "MaxFailureRatio": 0.3,
                                "Order": "start-first"
                            }
                        }
                        
                        async with session.post(update_url, json=update_data, headers=self.auth.get_headers(), ssl=self.ssl_verify) as resp:
                            if resp.status == 200:
                                _LOGGER.info("✅ Successfully updated stack service %s", service_name)
                                return True
                            else:
                                _LOGGER.error("❌ Failed to update stack service: HTTP %s", resp.status)
                                return False
                    else:
                        _LOGGER.error("❌ Failed to get service config: HTTP %s", resp.status)
                        return False
            except Exception as e:
                _LOGGER.error("❌ Error updating stack service: %s", e)
                return False

        except Exception as e:
            _LOGGER.exception("❌ Error updating stack container %s: %s", container_id, e)
            return False

    async def _recreate_standalone_container(self, endpoint_id: int, container_id: str, container_info: Dict[str, Any]):
        """Recreate a standalone container."""
        try:
            # Stop the container
            if not await self.stop_container(endpoint_id, container_id):
                _LOGGER.error("❌ Failed to stop container %s", container_id)
                return False

            # Remove the container
            remove_url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/containers/{container_id}?force=1"
            try:
                session = self.session or self.auth.session
                async with session.delete(remove_url, headers=self.auth.get_headers(), ssl=self.ssl_verify) as resp:
                    if resp.status != 204:
                        _LOGGER.error("❌ Failed to remove container %s: HTTP %s", container_id, resp.status)
                        return False
            except Exception as e:
                _LOGGER.error("❌ Error removing container %s: %s", container_id, e)
                return False

            # Create new container with same configuration
            create_url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/containers/create"
            
            # Prepare container configuration (simplified for standalone containers)
            container_config = {
                "Image": container_info["Config"]["Image"],
                "Cmd": container_info["Config"]["Cmd"],
                "Env": container_info["Config"]["Env"],
                "ExposedPorts": container_info["Config"]["ExposedPorts"],
                "Volumes": container_info["Config"]["Volumes"],
                "WorkingDir": container_info["Config"]["WorkingDir"],
                "Entrypoint": container_info["Config"]["Entrypoint"],
                "Labels": container_info["Config"]["Labels"],
                "HostConfig": {
                    "Binds": container_info["HostConfig"]["Binds"],
                    "PortBindings": container_info["HostConfig"]["PortBindings"],
                    "RestartPolicy": container_info["HostConfig"]["RestartPolicy"],
                    "NetworkMode": container_info["HostConfig"]["NetworkMode"],
                }
            }

            # Create new container
            try:
                session = self.session or self.auth.session
                async with session.post(create_url, json=container_config, headers=self.auth.get_headers(), ssl=self.ssl_verify) as resp:
                    if resp.status == 201:
                        create_response = await resp.json()
                        new_container_id = create_response["Id"]
                        
                        # Start the new container
                        if await self.start_container(endpoint_id, new_container_id):
                            _LOGGER.info("✅ Successfully recreated standalone container %s", container_id)
                            return True
                        else:
                            _LOGGER.error("❌ Failed to start recreated container %s", container_id)
                            return False
                    else:
                        _LOGGER.error("❌ Failed to create new container: HTTP %s", resp.status)
                        return False
            except Exception as e:
                _LOGGER.error("❌ Error creating new container: %s", e)
                return False

        except Exception as e:
            _LOGGER.exception("❌ Error recreating standalone container %s: %s", container_id, e)
            return False
