import logging
import aiohttp
from typing import Optional, Dict, Any

from .auth import PortainerAuth
from .container_api import PortainerContainerAPI
from .stack_api import PortainerStackAPI
from .image_api import PortainerImageAPI

_LOGGER = logging.getLogger(__name__)

class PortainerAPI:
    """Main Portainer API class that coordinates all operations."""

    def __init__(self, host: str, username: Optional[str] = None, 
                 password: Optional[str] = None, api_key: Optional[str] = None,
                 ssl_verify: bool = True, config: Optional[Dict[str, Any]] = None):
        """Initialize the Portainer API."""
        # Ensure host has proper scheme and format
        if not host.startswith(("http://", "https://")):
            # If no scheme provided, default to https
            host = f"https://{host}"
        
        self.base_url = host.rstrip("/")
        self.session: Optional[aiohttp.ClientSession] = None
        self.ssl_verify = ssl_verify
        self.config = config or {}
        
        _LOGGER.debug("🔧 Initializing Portainer API with base URL: %s", self.base_url)
        
        # Initialize authentication
        self.auth = PortainerAuth(self.base_url, username, password, api_key, ssl_verify)
        
        # Initialize API modules with the base URL
        self.containers = PortainerContainerAPI(self.base_url, self.auth, self.ssl_verify)
        self.stacks = PortainerStackAPI(self.base_url, self.auth, self.ssl_verify)
        self.images = PortainerImageAPI(self.base_url, self.auth, self.config, self.ssl_verify)

    async def initialize(self) -> bool:
        """Initialize the API connection."""
        try:
            # Create session with SSL verification setting
            connector = aiohttp.TCPConnector(ssl=self.ssl_verify)
            self.session = aiohttp.ClientSession(connector=connector)
            
            # Initialize authentication
            if not await self.auth.initialize(self.session):
                _LOGGER.error("❌ Failed to initialize authentication")
                return False
            
            _LOGGER.info("✅ Portainer API initialized successfully")
            return True
            
        except Exception as e:
            _LOGGER.exception("❌ Failed to initialize Portainer API: %s", e)
            return False

    async def close(self) -> None:
        """Close the API connection."""
        if self.session:
            await self.session.close()
            self.session = None

    # Container operations - delegate to container API
    async def get_containers(self, endpoint_id: int):
        """Get all containers for an endpoint."""
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
                async with self.auth.session.delete(remove_url, headers=self.auth.get_headers(), ssl=self.ssl_verify) as resp:
                    if resp.status != 204:
                        _LOGGER.error("❌ Failed to remove container %s: HTTP %s", container_id, resp.status)
                        return False
            except Exception as e:
                _LOGGER.error("❌ Error removing container %s: %s", container_id, e)
                return False

            # Create new container with same configuration but updated image
            create_url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/containers/create"
            
            # Prepare container configuration
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
                    "CapAdd": container_info["HostConfig"]["CapAdd"],
                    "CapDrop": container_info["HostConfig"]["CapDrop"],
                    "SecurityOpt": container_info["HostConfig"]["SecurityOpt"],
                    "Devices": container_info["HostConfig"]["Devices"],
                    "ExtraHosts": container_info["HostConfig"]["ExtraHosts"],
                    "VolumesFrom": container_info["HostConfig"]["VolumesFrom"],
                    "CpuShares": container_info["HostConfig"]["CpuShares"],
                    "Memory": container_info["HostConfig"]["Memory"],
                    "CgroupParent": container_info["HostConfig"]["CgroupParent"],
                    "BlkioWeight": container_info["HostConfig"]["BlkioWeight"],
                    "BlkioWeightDevice": container_info["HostConfig"]["BlkioWeightDevice"],
                    "BlkioDeviceReadBps": container_info["HostConfig"]["BlkioDeviceReadBps"],
                    "BlkioDeviceWriteBps": container_info["HostConfig"]["BlkioDeviceWriteBps"],
                    "BlkioDeviceReadIOps": container_info["HostConfig"]["BlkioDeviceReadIOps"],
                    "BlkioDeviceWriteIOps": container_info["HostConfig"]["BlkioDeviceWriteIOps"],
                    "CpuPeriod": container_info["HostConfig"]["CpuPeriod"],
                    "CpuQuota": container_info["HostConfig"]["CpuQuota"],
                    "CpuRealtimePeriod": container_info["HostConfig"]["CpuRealtimePeriod"],
                    "CpuRealtimeRuntime": container_info["HostConfig"]["CpuRealtimeRuntime"],
                    "CpusetCpus": container_info["HostConfig"]["CpusetCpus"],
                    "CpusetMems": container_info["HostConfig"]["CpusetMems"],
                    "Devices": container_info["HostConfig"]["Devices"],
                    "DeviceCgroupRules": container_info["HostConfig"]["DeviceCgroupRules"],
                    "DeviceRequests": container_info["HostConfig"]["DeviceRequests"],
                    "KernelMemory": container_info["HostConfig"]["KernelMemory"],
                    "KernelMemoryTCP": container_info["HostConfig"]["KernelMemoryTCP"],
                    "MemoryReservation": container_info["HostConfig"]["MemoryReservation"],
                    "MemorySwap": container_info["HostConfig"]["MemorySwap"],
                    "MemorySwappiness": container_info["HostConfig"]["MemorySwappiness"],
                    "NanoCpus": container_info["HostConfig"]["NanoCpus"],
                    "OomKillDisable": container_info["HostConfig"]["OomKillDisable"],
                    "PidsLimit": container_info["HostConfig"]["PidsLimit"],
                    "Ulimits": container_info["HostConfig"]["Ulimits"],
                    "CpuCount": container_info["HostConfig"]["CpuCount"],
                    "CpuPercent": container_info["HostConfig"]["CpuPercent"],
                    "IOMaximumIOps": container_info["HostConfig"]["IOMaximumIOps"],
                    "IOMaximumBandwidth": container_info["HostConfig"]["IOMaximumBandwidth"],
                }
            }

            # Create new container
            try:
                async with self.auth.session.post(create_url, json=container_config, headers=self.auth.get_headers(), ssl=self.ssl_verify) as resp:
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
                async with self.auth.session.get(service_url, headers=self.auth.get_headers(), ssl=self.ssl_verify) as resp:
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
                        
                        async with self.auth.session.post(update_url, json=update_data, headers=self.auth.get_headers(), ssl=self.ssl_verify) as resp:
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
                async with self.auth.session.delete(remove_url, headers=self.auth.get_headers(), ssl=self.ssl_verify) as resp:
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
                async with self.auth.session.post(create_url, json=container_config, headers=self.auth.get_headers(), ssl=self.ssl_verify) as resp:
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
