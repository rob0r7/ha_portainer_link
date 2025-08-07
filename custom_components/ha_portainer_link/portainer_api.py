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
                 password: Optional[str] = None, api_key: Optional[str] = None):
        """Initialize the Portainer API."""
        self.base_url = host.rstrip("/")
        self.session: Optional[aiohttp.ClientSession] = None
        
        # Initialize authentication
        self.auth = PortainerAuth(host, username, password, api_key)
        
        # Initialize API modules
        self.containers = PortainerContainerAPI(self.base_url, self.auth)
        self.stacks = PortainerStackAPI(self.base_url, self.auth)
        self.images = PortainerImageAPI(self.base_url, self.auth)

    async def initialize(self) -> bool:
        """Initialize the API connection."""
        try:
            # Create session
            self.session = aiohttp.ClientSession()
            
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
        """Check if a container's image has updates available."""
        return await self.images.check_image_updates(endpoint_id, container_id)

    async def pull_image_update(self, endpoint_id: int, container_id: str):
        """Pull the latest image for a container."""
        return await self.images.pull_image_update(endpoint_id, container_id)

    async def get_image_info(self, endpoint_id: int, image_id: str):
        """Get detailed information about a Docker image."""
        return await self.images.get_image_info(endpoint_id, image_id)

    def extract_version_from_image(self, image_data: Dict[str, Any]):
        """Extract version information from image data."""
        return self.images.extract_version_from_image(image_data)

    async def get_available_version(self, endpoint_id: int, image_name: str):
        """Get the available version from the registry."""
        return await self.images.get_available_version(endpoint_id, image_name)

    # Legacy methods for backward compatibility
    async def get_container_info(self, endpoint_id: int, container_id: str):
        """Get detailed container information including image details."""
        return await self.containers.inspect_container(endpoint_id, container_id)

    async def get_container_image_name(self, endpoint_id: int, container_id: str):
        """Get the image name for a container."""
        try:
            container_info = await self.containers.inspect_container(endpoint_id, container_id)
            if container_info:
                return container_info.get("Config", {}).get("Image")
            return None
        except Exception as e:
            _LOGGER.exception("Error getting image name for container %s: %s", container_id, e)
            return None

    # Container recreation methods (keeping these in main class for now)
    async def recreate_container_with_new_image(self, endpoint_id: int, container_id: str):
        """Recreate a container with the latest image."""
        try:
            _LOGGER.info("🔄 Starting container recreation for %s", container_id)
            
            # Get current container configuration
            container_info = await self.containers.inspect_container(endpoint_id, container_id)
            if not container_info:
                _LOGGER.error("No container info found for %s", container_id)
                return False
            
            # Check if container is part of a stack
            labels = container_info.get("Config", {}).get("Labels", {})
            stack_name = labels.get("com.docker.compose.project")
            
            if stack_name:
                _LOGGER.info("📦 Container %s is part of stack %s - using stack update", container_id, stack_name)
                return await self._update_stack_container(endpoint_id, container_id, stack_name)
            else:
                _LOGGER.info("🏠 Container %s is standalone - using direct recreation", container_id)
                return await self._recreate_standalone_container(endpoint_id, container_id, container_info)
                    
        except Exception as e:
            _LOGGER.exception("❌ Error recreating container %s: %s", container_id, e)
            return False

    async def _update_stack_container(self, endpoint_id: int, container_id: str, stack_name: str):
        """Update a container that's part of a stack by updating the entire stack."""
        try:
            _LOGGER.info("🔄 Updating stack %s to refresh container %s", stack_name, container_id)
            
            # Get stack information
            stacks_data = await self.stacks.get_stacks(endpoint_id)
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
            
            async with self.session.put(update_url, headers=self.auth.get_headers(), json=update_payload) as resp:
                if resp.status == 200:
                    _LOGGER.info("✅ Successfully updated stack %s", stack_name)
                    return True
                else:
                    _LOGGER.error("❌ Failed to update stack %s: %s", stack_name, resp.status)
                    return False
                    
        except Exception as e:
            _LOGGER.exception("❌ Error updating stack %s: %s", stack_name, e)
            return False

    async def _recreate_standalone_container(self, endpoint_id: int, container_id: str, container_info: Dict[str, Any]):
        """Recreate a standalone container with the latest image."""
        try:
            # Extract container configuration
            config = container_info.get("Config", {})
            host_config = container_info.get("HostConfig", {})
            
            # Get the image name
            image_name = config.get("Image")
            if not image_name:
                _LOGGER.error("No image name found for container %s", container_id)
                return False
            
            # Get container name
            container_name = container_info.get("Name", "").lstrip("/")
            if not container_name:
                _LOGGER.error("No container name found for %s", container_id)
                return False
            
            _LOGGER.info("📋 Recreating standalone container %s with image %s", container_name, image_name)
            
            # Stop the current container
            _LOGGER.info("⏹️ Stopping container %s", container_name)
            stop_url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/containers/{container_id}/stop"
            async with self.session.post(stop_url, headers=self.auth.get_headers()) as resp:
                if resp.status not in [204, 304]:  # 304 means already stopped
                    _LOGGER.warning("Could not stop container %s: %s", container_name, resp.status)
            
            # Wait a moment for the container to stop
            import asyncio
            await asyncio.sleep(2)
            
            # Remove the old container
            _LOGGER.info("🗑️ Removing old container %s", container_name)
            remove_url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/containers/{container_id}?force=1"
            async with self.session.delete(remove_url, headers=self.auth.get_headers()) as resp:
                if resp.status not in [204, 404]:  # 404 means already removed
                    _LOGGER.warning("Could not remove container %s: %s", container_name, resp.status)
            
            # Wait a moment for removal to complete
            await asyncio.sleep(2)
            
            # Create new container with the same configuration
            _LOGGER.info("🏗️ Creating new container %s", container_name)
            create_url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/containers/create"
            
            # Prepare container creation payload with ALL original configuration
            create_payload = {
                "Image": image_name,
                "name": container_name,
                "Cmd": config.get("Cmd", []),
                "Entrypoint": config.get("Entrypoint", []),
                "Env": config.get("Env", []),
                "WorkingDir": config.get("WorkingDir", ""),
                "Labels": config.get("Labels", {}),
                "ExposedPorts": config.get("ExposedPorts", {}),
                "Hostname": config.get("Hostname", ""),
                "Domainname": config.get("Domainname", ""),
                "User": config.get("User", ""),
                "AttachStdin": config.get("AttachStdin", False),
                "AttachStdout": config.get("AttachStdout", False),
                "AttachStderr": config.get("AttachStderr", False),
                "Tty": config.get("Tty", False),
                "OpenStdin": config.get("OpenStdin", False),
                "StdinOnce": config.get("StdinOnce", False),
                "HostConfig": {
                    "Binds": host_config.get("Binds", []),
                    "NetworkMode": host_config.get("NetworkMode", "default"),
                    "RestartPolicy": host_config.get("RestartPolicy", {}),
                    "PortBindings": host_config.get("PortBindings", {}),
                    "VolumesFrom": host_config.get("VolumesFrom", []),
                    "CapAdd": host_config.get("CapAdd", []),
                    "CapDrop": host_config.get("CapDrop", []),
                    "Dns": host_config.get("Dns", []),
                    "DnsOptions": host_config.get("DnsOptions", []),
                    "DnsSearch": host_config.get("DnsSearch", []),
                    "ExtraHosts": host_config.get("ExtraHosts", []),
                    "GroupAdd": host_config.get("GroupAdd", []),
                    "IpcMode": host_config.get("IpcMode", ""),
                    "Cgroup": host_config.get("Cgroup", ""),
                    "Links": host_config.get("Links", []),
                    "OomScoreAdj": host_config.get("OomScoreAdj", 0),
                    "PidMode": host_config.get("PidMode", ""),
                    "Privileged": host_config.get("Privileged", False),
                    "PublishAllPorts": host_config.get("PublishAllPorts", False),
                    "ReadonlyRootfs": host_config.get("ReadonlyRootfs", False),
                    "SecurityOpt": host_config.get("SecurityOpt", []),
                    "StorageOpt": host_config.get("StorageOpt", {}),
                    "Tmpfs": host_config.get("Tmpfs", {}),
                    "UTSMode": host_config.get("UTSMode", ""),
                    "UsernsMode": host_config.get("UsernsMode", ""),
                    "ShmSize": host_config.get("ShmSize", 0),
                    "Sysctls": host_config.get("Sysctls", {}),
                    "Runtime": host_config.get("Runtime", ""),
                    "ConsoleSize": host_config.get("ConsoleSize", [0, 0]),
                    "Isolation": host_config.get("Isolation", ""),
                    "CpuShares": host_config.get("CpuShares", 0),
                    "Memory": host_config.get("Memory", 0),
                    "NanoCpus": host_config.get("NanoCpus", 0),
                    "CgroupParent": host_config.get("CgroupParent", ""),
                    "BlkioWeight": host_config.get("BlkioWeight", 0),
                    "BlkioWeightDevice": host_config.get("BlkioWeightDevice", []),
                    "BlkioDeviceReadBps": host_config.get("BlkioDeviceReadBps", []),
                    "BlkioDeviceWriteBps": host_config.get("BlkioDeviceWriteBps", []),
                    "BlkioDeviceReadIOps": host_config.get("BlkioDeviceReadIOps", []),
                    "BlkioDeviceWriteIOps": host_config.get("BlkioDeviceWriteIOps", []),
                    "CpuPeriod": host_config.get("CpuPeriod", 0),
                    "CpuQuota": host_config.get("CpuQuota", 0),
                    "CpuRealtimePeriod": host_config.get("CpuRealtimePeriod", 0),
                    "CpuRealtimeRuntime": host_config.get("CpuRealtimeRuntime", 0),
                    "CpusetCpus": host_config.get("CpusetCpus", ""),
                    "CpusetMems": host_config.get("CpusetMems", ""),
                    "Devices": host_config.get("Devices", []),
                    "DeviceCgroupRules": host_config.get("DeviceCgroupRules", []),
                    "DeviceRequests": host_config.get("DeviceRequests", []),
                    "KernelMemory": host_config.get("KernelMemory", 0),
                    "KernelMemoryTCP": host_config.get("KernelMemoryTCP", 0),
                    "MemoryReservation": host_config.get("MemoryReservation", 0),
                    "MemorySwap": host_config.get("MemorySwap", 0),
                    "MemorySwappiness": host_config.get("MemorySwappiness", None),
                    "OomKillDisable": host_config.get("OomKillDisable", False),
                    "PidsLimit": host_config.get("PidsLimit", 0),
                    "Ulimits": host_config.get("Ulimits", []),
                    "CpuCount": host_config.get("CpuCount", 0),
                    "CpuPercent": host_config.get("CpuPercent", 0),
                    "IOMaximumIOps": host_config.get("IOMaximumIOps", 0),
                    "IOMaximumBandwidth": host_config.get("IOMaximumBandwidth", 0),
                    "MaskedPaths": host_config.get("MaskedPaths", []),
                    "ReadonlyPaths": host_config.get("ReadonlyPaths", [])
                }
            }
            
            async with self.session.post(create_url, headers=self.auth.get_headers(), json=create_payload) as resp:
                if resp.status == 201:
                    new_container_data = await resp.json()
                    new_container_id = new_container_data.get("Id")
                    _LOGGER.info("✅ Successfully created new container %s with ID %s", container_name, new_container_id)
                    
                    # Start the new container
                    _LOGGER.info("▶️ Starting new container %s", container_name)
                    start_url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/containers/{new_container_id}/start"
                    async with self.session.post(start_url, headers=self.auth.get_headers()) as resp:
                        if resp.status == 204:
                            _LOGGER.info("✅ Successfully started new container %s", container_name)
                            return True
                        else:
                            _LOGGER.error("❌ Failed to start new container %s: %s", container_name, resp.status)
                            return False
                else:
                    _LOGGER.error("❌ Failed to create new container %s: %s", container_name, resp.status)
                    return False
                    
        except Exception as e:
            _LOGGER.exception("❌ Error recreating standalone container %s: %s", container_id, e)
            return False
