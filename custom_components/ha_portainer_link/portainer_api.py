import logging
import asyncio
import aiohttp

_LOGGER = logging.getLogger(__name__)

class PortainerAPI:
    def __init__(self, host, username=None, password=None, api_key=None):
        self.base_url = host.rstrip("/")
        self.username = username
        self.password = password
        self.api_key = api_key
        self.token = None
        self.session = aiohttp.ClientSession()
        self.headers = {}

    async def initialize(self):
        if self.api_key:
            self.headers = {
                "X-API-Key": self.api_key,
                "Content-Type": "application/json",
            }
        elif self.username and self.password:
            await self.authenticate()
        else:
            _LOGGER.error("[PortainerAPI] No credentials provided.")

    async def authenticate(self):
        url = f"{self.base_url}/api/auth"
        payload = {"Username": self.username, "Password": self.password}
        try:
            async with self.session.post(url, json=payload, ssl=False) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    self.token = data.get("jwt")
                    self.headers = {
                        "Authorization": f"Bearer {self.token}",
                        "Content-Type": "application/json",
                    }
                    _LOGGER.info("[PortainerAPI] Authentifiziert.")
                else:
                    _LOGGER.error("[PortainerAPI] Authentifizierung fehlgeschlagen: %s", resp.status)
        except Exception as e:
            _LOGGER.exception("[PortainerAPI] Fehler bei Authentifizierung: %s", e)

    async def get_containers(self, endpoint_id):
        url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/containers/json?all=1"
        try:
            async with self.session.get(url, headers=self.headers, ssl=False) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    _LOGGER.error("[PortainerAPI] Fehler beim Abruf der Container: %s", resp.status)
                    return []
        except Exception as e:
            _LOGGER.exception("[PortainerAPI] Fehler beim Abrufen der Container: %s", e)
            return []

    async def restart_container(self, endpoint_id, container_id):
        url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/containers/{container_id}/restart"
        try:
            async with self.session.post(url, headers=self.headers, ssl=False) as resp:
                return resp.status == 204
        except Exception as e:
            _LOGGER.exception("[PortainerAPI] Fehler beim Neustart von Container %s: %s", container_id, e)
            return False

    async def inspect_container(self, endpoint_id, container_id):
        url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/containers/{container_id}/json"
        try:
            async with self.session.get(url, headers=self.headers, ssl=False) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    _LOGGER.error("[PortainerAPI] Fehler bei Inspect von Container: %s", resp.status)
                    return {}
        except Exception as e:
            _LOGGER.exception("[PortainerAPI] Fehler bei Inspect: %s", e)
            return {}

    async def get_container_stats(self, endpoint_id, container_id):
        url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/containers/{container_id}/stats?stream=false"
        try:
            async with self.session.get(url, headers=self.headers, ssl=False) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    _LOGGER.error("[PortainerAPI] Failed to get stats: %s", resp.status)
                    return {}
        except Exception as e:
            _LOGGER.exception("[PortainerAPI] Exception getting stats: %s", e)
            return {}
        
    async def start_container(self, endpoint_id, container_id):
        url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/containers/{container_id}/start"
        try:
            async with self.session.post(url, headers=self.headers, ssl=False) as resp:
                return resp.status == 204
        except Exception as e:
            _LOGGER.exception("Exception while starting container %s: %s", container_id, e)
            return False

    async def stop_container(self, endpoint_id, container_id):
        url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/containers/{container_id}/stop"
        try:
            async with self.session.post(url, headers=self.headers, ssl=False) as resp:
                return resp.status == 204
        except Exception as e:
            _LOGGER.exception("Exception while stopping container %s: %s", container_id, e)
            return False

    async def get_container_info(self, endpoint_id, container_id):
        """Get detailed container information including image details."""
        return await self.inspect_container(endpoint_id, container_id)

    async def check_image_updates(self, endpoint_id, container_id):
        """Check if a container's image has updates available by actually pulling from registry."""
        try:
            # Get container inspection data
            container_info = await self.inspect_container(endpoint_id, container_id)
            if not container_info:
                _LOGGER.debug("No container info found for %s", container_id)
                return False
            
            # Extract image information
            image_name = container_info.get("Config", {}).get("Image")
            if not image_name:
                _LOGGER.debug("No image name found for container %s", container_id)
                return False
            
            _LOGGER.debug("🔍 Checking updates for container %s with image: %s", container_id, image_name)
            
            # Get current image digest
            current_image_id = container_info.get("Image")
            if not current_image_id:
                _LOGGER.debug("No current image ID found for container %s", container_id)
                return False
            
            # Get current image details
            current_image_url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/images/{current_image_id}/json"
            async with self.session.get(current_image_url, headers=self.headers, ssl=False) as resp:
                if resp.status != 200:
                    _LOGGER.debug("Could not get current image info: %s", resp.status)
                    return False
                current_image_data = await resp.json()
                current_digest = current_image_data.get("Id", "")
            
            _LOGGER.debug("Current image digest: %s", current_digest[:12] if current_digest else "unknown")
            
            # Try to pull the latest image from registry
            pull_url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/images/create"
            params = {"fromImage": image_name}
            
            _LOGGER.debug("📥 Pulling latest image from registry: %s", image_name)
            async with self.session.post(pull_url, headers=self.headers, params=params, ssl=False) as resp:
                if resp.status == 200:
                    _LOGGER.debug("✅ Successfully pulled image from registry")
                    
                    # Get the newly pulled image digest
                    images_url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/images/json"
                    async with self.session.get(images_url, headers=self.headers, ssl=False) as resp2:
                        if resp2.status == 200:
                            images_data = await resp2.json()
                            # Find the image with the same name but potentially different digest
                            for image in images_data:
                                repo_tags = image.get("RepoTags", [])
                                if image_name in repo_tags:
                                    new_digest = image.get("Id", "")
                                    _LOGGER.debug("New image digest: %s", new_digest[:12] if new_digest else "unknown")
                                    
                                    # Compare digests to see if there's an update
                                    has_update = new_digest != current_digest
                                    _LOGGER.info("Update check for %s: %s (current: %s, new: %s)", 
                                               image_name, has_update, 
                                               current_digest[:12] if current_digest else "unknown",
                                               new_digest[:12] if new_digest else "unknown")
                                    
                                    # If we found a different digest, there's an update
                                    if has_update:
                                        _LOGGER.info("✅ Update available for %s: digest changed from %s to %s", 
                                                   image_name, 
                                                   current_digest[:12] if current_digest else "unknown",
                                                   new_digest[:12] if new_digest else "unknown")
                                    else:
                                        _LOGGER.info("ℹ️ No update available for %s: same digest %s", 
                                                   image_name, 
                                                   current_digest[:12] if current_digest else "unknown")
                                    
                                    return has_update
                    
                    _LOGGER.warning("⚠️ Could not find image %s after pull", image_name)
                    return False
                elif resp.status == 401:
                    _LOGGER.warning("⚠️ Authentication required for registry %s", image_name.split('/')[0])
                    return False
                elif resp.status == 403:
                    _LOGGER.warning("⚠️ Access forbidden for registry %s", image_name.split('/')[0])
                    return False
                elif resp.status == 404:
                    _LOGGER.warning("⚠️ Image %s not found in registry", image_name)
                    return False
                elif resp.status == 429:
                    _LOGGER.warning("⚠️ Rate limit exceeded for registry %s", image_name.split('/')[0])
                    return False
                elif resp.status == 500:
                    _LOGGER.warning("⚠️ Registry server error for %s", image_name)
                    return False
                else:
                    _LOGGER.warning("⚠️ Failed to pull image %s: HTTP %s", image_name, resp.status)
                    return False
        except aiohttp.ClientConnectorError as e:
            _LOGGER.warning("⚠️ Network error connecting to registry for %s: %s", container_id, e)
            return False
        except aiohttp.ClientTimeout as e:
            _LOGGER.warning("⚠️ Timeout connecting to registry for %s: %s", container_id, e)
            return False
        except Exception as e:
            _LOGGER.exception("❌ Error checking image updates for container %s: %s", container_id, e)
            return False



    async def pull_image_update(self, endpoint_id, container_id):
        """Pull the latest image for a container."""
        try:
            # Get container inspection data to find the image
            container_info = await self.inspect_container(endpoint_id, container_id)
            if not container_info:
                _LOGGER.error("No container info found for %s", container_id)
                return False
            
            # Extract image information
            image_name = container_info.get("Config", {}).get("Image")
            if not image_name:
                _LOGGER.error("No image name found for container %s", container_id)
                return False
            
            _LOGGER.info("Pulling latest image for container %s: %s", container_id, image_name)
            
            # Pull the latest image
            url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/images/create"
            params = {"fromImage": image_name}
            
            async with self.session.post(url, headers=self.headers, params=params, ssl=False) as resp:
                if resp.status == 200:
                    _LOGGER.info("✅ Successfully pulled image update for container %s (%s)", container_id, image_name)
                    return True
                else:
                    _LOGGER.error("❌ Failed to pull image update for container %s: %s", container_id, resp.status)
                    return False
        except Exception as e:
            _LOGGER.exception("❌ Error pulling image update for container %s: %s", container_id, e)
            return False

    async def recreate_container_with_new_image(self, endpoint_id, container_id):
        """Recreate a container with the latest image."""
        try:
            _LOGGER.info("🔄 Starting container recreation for %s", container_id)
            
            # Get current container configuration
            container_info = await self.inspect_container(endpoint_id, container_id)
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

    async def _update_stack_container(self, endpoint_id, container_id, stack_name):
        """Update a container that's part of a stack by updating the entire stack."""
        try:
            _LOGGER.info("🔄 Updating stack %s to refresh container %s", stack_name, container_id)
            
            # Get stack information
            stacks_url = f"{self.base_url}/api/stacks"
            async with self.session.get(stacks_url, headers=self.headers, ssl=False) as resp:
                if resp.status != 200:
                    _LOGGER.error("Could not get stacks list: %s", resp.status)
                    return False
                
                stacks_data = await resp.json()
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
            
            async with self.session.put(update_url, headers=self.headers, json=update_payload, ssl=False) as resp:
                if resp.status == 200:
                    _LOGGER.info("✅ Successfully updated stack %s", stack_name)
                    return True
                else:
                    _LOGGER.error("❌ Failed to update stack %s: %s", stack_name, resp.status)
                    return False
                    
        except Exception as e:
            _LOGGER.exception("❌ Error updating stack %s: %s", stack_name, e)
            return False

    async def _recreate_standalone_container(self, endpoint_id, container_id, container_info):
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
            async with self.session.post(stop_url, headers=self.headers, ssl=False) as resp:
                if resp.status not in [204, 304]:  # 304 means already stopped
                    _LOGGER.warning("Could not stop container %s: %s", container_name, resp.status)
            
            # Wait a moment for the container to stop
            await asyncio.sleep(2)
            
            # Remove the old container
            _LOGGER.info("🗑️ Removing old container %s", container_name)
            remove_url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/containers/{container_id}?force=1"
            async with self.session.delete(remove_url, headers=self.headers, ssl=False) as resp:
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
            
            async with self.session.post(create_url, headers=self.headers, json=create_payload, ssl=False) as resp:
                if resp.status == 201:
                    new_container_data = await resp.json()
                    new_container_id = new_container_data.get("Id")
                    _LOGGER.info("✅ Successfully created new container %s with ID %s", container_name, new_container_id)
                    
                    # Start the new container
                    _LOGGER.info("▶️ Starting new container %s", container_name)
                    start_url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/containers/{new_container_id}/start"
                    async with self.session.post(start_url, headers=self.headers, ssl=False) as resp:
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

    async def get_container_image_name(self, endpoint_id, container_id):
        """Get the image name for a container."""
        try:
            container_info = await self.inspect_container(endpoint_id, container_id)
            if container_info:
                return container_info.get("Config", {}).get("Image")
            return None
        except Exception as e:
            _LOGGER.exception("Error getting image name for container %s: %s", container_id, e)
            return None

    async def get_image_info(self, endpoint_id, image_id):
        """Get detailed information about a Docker image."""
        try:
            url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/images/{image_id}/json"
            async with self.session.get(url, headers=self.headers, ssl=False) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    _LOGGER.debug("Could not get image info for %s: %s", image_id, resp.status)
                    return None
        except Exception as e:
            _LOGGER.exception("Error getting image info for %s: %s", image_id, e)
            return None

    def extract_version_from_image(self, image_data):
        """Extract version information from image data."""
        try:
            # Try to get version from RepoTags
            repo_tags = image_data.get("RepoTags", [])
            if repo_tags:
                # Look for version tags (not 'latest')
                for tag in repo_tags:
                    if ':' in tag and not tag.endswith(':latest'):
                        version = tag.split(':')[-1]
                        if version and version != 'latest':
                            return version
                
                # If no version tag found, try to get from digest
                repo_digests = image_data.get("RepoDigests", [])
                if repo_digests:
                    # Extract digest (first 12 characters)
                    digest = repo_digests[0].split('@')[-1]
                    return digest[:12] if digest else "unknown"
                
                # For :latest tags, show the digest to indicate it's the latest
                if any(tag.endswith(':latest') for tag in repo_tags):
                    image_id = image_data.get("Id", "")
                    if image_id:
                        return f"latest ({image_id[:12]})"
                    return "latest"
            
            # If no tags, try to get from image ID
            image_id = image_data.get("Id", "")
            if image_id:
                return image_id[:12]
            
            return "unknown"
        except Exception as e:
            _LOGGER.debug("Error extracting version from image: %s", e)
            return "unknown"

    async def get_available_version(self, endpoint_id, image_name):
        """Get the available version from the registry."""
        try:
            _LOGGER.debug("🔍 Checking available version for %s", image_name)
            
            # Pull the latest image to get registry info
            pull_url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/images/create"
            params = {"fromImage": image_name}
            
            async with self.session.post(pull_url, headers=self.headers, params=params, ssl=False) as resp:
                if resp.status == 200:
                    _LOGGER.debug("✅ Successfully pulled image %s from registry", image_name)
                    
                    # Get the newly pulled image info
                    images_url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/images/json"
                    async with self.session.get(images_url, headers=self.headers, ssl=False) as resp2:
                        if resp2.status == 200:
                            images_data = await resp2.json()
                            # Find the image with the same name
                            for image in images_data:
                                repo_tags = image.get("RepoTags", [])
                                if image_name in repo_tags:
                                    version = self.extract_version_from_image(image)
                                    _LOGGER.debug("✅ Available version for %s: %s", image_name, version)
                                    return version
                    
                    _LOGGER.warning("⚠️ Could not find image %s after pull", image_name)
                    return "unknown (not found after pull)"
                elif resp.status == 401:
                    _LOGGER.warning("⚠️ Authentication required for registry %s", image_name.split('/')[0])
                    return "unknown (auth required)"
                elif resp.status == 403:
                    _LOGGER.warning("⚠️ Access forbidden for registry %s", image_name.split('/')[0])
                    return "unknown (access forbidden)"
                elif resp.status == 404:
                    _LOGGER.warning("⚠️ Image %s not found in registry", image_name)
                    return "unknown (not in registry)"
                elif resp.status == 429:
                    _LOGGER.warning("⚠️ Rate limit exceeded for registry %s", image_name.split('/')[0])
                    return "unknown (rate limited)"
                elif resp.status == 500:
                    _LOGGER.warning("⚠️ Registry server error for %s", image_name)
                    return "unknown (registry error)"
                else:
                    _LOGGER.warning("⚠️ Failed to pull image %s: HTTP %s", image_name, resp.status)
                    return f"unknown (HTTP {resp.status})"
        except aiohttp.ClientConnectorError as e:
            _LOGGER.warning("⚠️ Network error connecting to registry for %s: %s", image_name, e)
            return "unknown (network error)"
        except aiohttp.ClientTimeout as e:
            _LOGGER.warning("⚠️ Timeout connecting to registry for %s: %s", image_name, e)
            return "unknown (timeout)"
        except Exception as e:
            _LOGGER.warning("⚠️ Error getting available version for %s: %s", image_name, e)
            return "unknown (error)"
