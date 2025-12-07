import logging
import asyncio
import aiohttp

from .image_api import PortainerImageAPI
from .container_api import PortainerContainerAPI
from .stack_api import PortainerStackAPI

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
        # Initialize modular APIs (share session + headers via self)
        try:
            self.images = PortainerImageAPI(self.base_url, self, ssl_verify=False, session=self.session)
            self.containers = PortainerContainerAPI(self.base_url, self, ssl_verify=False, session=self.session)
            self.stacks_api = PortainerStackAPI(self.base_url, self, ssl_verify=False, session=self.session)
        except Exception as e:
            _LOGGER.exception("❌ Failed to initialize sub-APIs: %s", e)

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
        # Initialize modular APIs (share session + headers via self)
        try:
            self.images = PortainerImageAPI(self.base_url, self, ssl_verify=False, session=self.session)
            self.containers = PortainerContainerAPI(self.base_url, self, ssl_verify=False, session=self.session)
            self.stacks_api = PortainerStackAPI(self.base_url, self, ssl_verify=False, session=self.session)
        except Exception as e:
            _LOGGER.exception("❌ Failed to initialize sub-APIs: %s", e)

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
        # Prefer modular API if available
        try:
            if hasattr(self, "containers") and self.containers:
                containers = await self.containers.get_containers(endpoint_id)
                return containers or []
        except Exception as e:
            _LOGGER.debug("Falling back to legacy get_containers due to: %s", e)
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
        # Prefer modular API if available
        try:
            if hasattr(self, "containers") and self.containers:
                data = await self.containers.inspect_container(endpoint_id, container_id)
                return data or {}
        except Exception as e:
            _LOGGER.debug("Falling back to legacy inspect_container due to: %s", e)
        url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/containers/{container_id}/json"
        try:
            async with self.session.get(url, headers=self.headers, ssl=False) as resp:
                if resp.status == 200:
                    container_data = await resp.json()
                    _LOGGER.debug("✅ Successfully inspected container %s", container_id)
                    return container_data
                else:
                    _LOGGER.error("❌ Failed to inspect container %s: HTTP %s", container_id, resp.status)
                    return {}
        except Exception as e:
            _LOGGER.exception("❌ Exception inspecting container %s: %s", container_id, e)
            return {}

    async def get_container_stats(self, endpoint_id, container_id):
        # Prefer modular API if available
        try:
            if hasattr(self, "containers") and self.containers:
                data = await self.containers.get_container_stats(endpoint_id, container_id)
                return data or {}
        except Exception:
            pass
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
        # Delegate to modular API if available
        try:
            if hasattr(self, "containers") and self.containers:
                return await self.containers.start_container(endpoint_id, container_id)
        except Exception:
            pass
        url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/containers/{container_id}/start"
        try:
            async with self.session.post(url, headers=self.headers, ssl=False) as resp:
                return resp.status == 204
        except Exception as e:
            _LOGGER.exception("Exception while starting container %s: %s", container_id, e)
            return False

    async def stop_container(self, endpoint_id, container_id):
        # Delegate to modular API if available
        try:
            if hasattr(self, "containers") and self.containers:
                return await self.containers.stop_container(endpoint_id, container_id)
        except Exception:
            pass
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

    # ---------------------------
    # Image helpers (delegated to PortainerImageAPI)
    # ---------------------------
    async def check_image_updates(self, endpoint_id, container_id):
        """Check if a container's image has updates available without pulling images."""
        try:
            if hasattr(self, "images") and self.images:
                return await self.images.check_image_updates(endpoint_id, container_id)
        except Exception as e:
            _LOGGER.debug("Image sub-API check failed, falling back to legacy pull-based method: %s", e)
        # Legacy pull-based fallback
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
                                    return has_update
                    _LOGGER.warning("⚠️ Could not find image %s after pull", image_name)
                    return False
                else:
                    _LOGGER.warning("⚠️ Failed to pull image %s: HTTP %s", image_name, resp.status)
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

    # ---------------------------
    # Convenience wrappers for image metadata (delegate to self.images)
    # ---------------------------
    async def get_image_info(self, endpoint_id, image_id):
        try:
            if hasattr(self, "images") and self.images:
                return await self.images.get_image_info(endpoint_id, image_id)
        except Exception:
            pass
        # Legacy fallback
        url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/images/{image_id}/json"
        async with self.session.get(url, headers=self.headers, ssl=False) as resp:
            if resp.status == 200:
                return await resp.json()
            return None

    def extract_version_from_image(self, image_data):
        try:
            if hasattr(self, "images") and self.images:
                return self.images.extract_version_from_image(image_data)
        except Exception:
            pass
        # Legacy fallback
        try:
            repo_tags = image_data.get("RepoTags", [])
            if repo_tags:
                for tag in repo_tags:
                    if ':' in tag and not tag.endswith(':latest'):
                        version = tag.split(':')[-1]
                        if version and version != 'latest':
                            return version
                repo_digests = image_data.get("RepoDigests", [])
                if repo_digests:
                    digest = repo_digests[0].split('@')[-1]
                    return digest[:12] if digest else "unknown"
                if any(tag.endswith(':latest') for tag in repo_tags):
                    image_id = image_data.get("Id", "")
                    if image_id:
                        return f"latest ({image_id[:12]})"
                    return "latest"
            image_id = image_data.get("Id", "")
            if image_id:
                return image_id[:12]
            return "unknown"
        except Exception as e:
            _LOGGER.debug("Error extracting version from image: %s", e)
            return "unknown"

    async def get_available_version(self, endpoint_id, image_name):
        try:
            if hasattr(self, "images") and self.images:
                return await self.images.get_available_version(endpoint_id, image_name)
        except Exception:
            pass
        # Legacy fallback
        _LOGGER.debug("🔍 Checking available version for %s", image_name)
        images_url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/images/json"
        async with self.session.get(images_url, headers=self.headers, ssl=False) as resp:
            if resp.status == 200:
                images_data = await resp.json()
                for image in images_data:
                    repo_tags = image.get("RepoTags", [])
                    if image_name in repo_tags:
                        return self.extract_version_from_image(image)
        return "unknown"

    async def get_current_digest(self, endpoint_id, container_id):
        try:
            if hasattr(self, "images") and self.images:
                return await self.images.get_current_digest(endpoint_id, container_id)
        except Exception:
            pass
        # Legacy fallback
        try:
            container_info = await self.inspect_container(endpoint_id, container_id)
            if not container_info:
                return "unknown"
            current_image_id = container_info.get("Image")
            if not current_image_id:
                return "unknown"
            current_image_url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/images/{current_image_id}/json"
            async with self.session.get(current_image_url, headers=self.headers, ssl=False) as resp:
                if resp.status != 200:
                    return "unknown"
                current_image_data = await resp.json()
                repo_digests = current_image_data.get("RepoDigests") or []
                digest = (repo_digests[0] if repo_digests else current_image_data.get("Id", ""))
                if digest:
                    short = (digest.split("@")[-1] if "@" in digest else digest).split(":")[-1][:12]
                    return short
                return "unknown"
        except Exception:
            return "unknown"

    async def get_available_digest(self, endpoint_id, container_id):
        try:
            if hasattr(self, "images") and self.images:
                return await self.images.get_available_digest(endpoint_id, container_id)
        except Exception:
            pass
        return "unknown"

    async def get_stacks(self, endpoint_id):
        """List stacks for an endpoint (delegates to stacks API)."""
        try:
            if hasattr(self, "stacks_api") and self.stacks_api:
                return await self.stacks_api.get_stacks(endpoint_id)
        except Exception as e:
            _LOGGER.debug("Falling back: stacks API failed: %s", e)
        # Legacy fallback (all stacks, not filtered)
        try:
            stacks_url = f"{self.base_url}/api/stacks"
            async with self.session.get(stacks_url, headers=self.headers, ssl=False) as resp:
                if resp.status == 200:
                    stacks = await resp.json()
                    # Filter by endpoint if possible
                    return [s for s in stacks if s.get("EndpointId") == endpoint_id]
                else:
                    _LOGGER.error("Could not get stacks list: %s", resp.status)
                    return []
        except Exception as e:
            _LOGGER.exception("Error getting stacks: %s", e)
            return []

    def get_container_stack_info(self, container_info):
        """Extract stack information from container info."""
        try:
            if hasattr(self, "containers") and self.containers and hasattr(self.containers, "get_container_stack_info"):
                return self.containers.get_container_stack_info(container_info)
        except Exception:
            pass
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
            _LOGGER.debug("🔍 Stack detection for container: stack_name=%s, service=%s, number=%s", 
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

    async def stop_stack(self, endpoint_id, stack_name):
        """Stop all containers in a stack."""
        try:
            _LOGGER.info("🛑 Stopping stack %s", stack_name)
            
            # Get all containers in the stack
            containers_url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/containers/json?all=1"
            async with self.session.get(containers_url, headers=self.headers, ssl=False) as resp:
                if resp.status != 200:
                    _LOGGER.error("Could not get containers list: %s", resp.status)
                    return False
                
                containers_data = await resp.json()
                stack_containers = []
                
                # Find all containers belonging to this stack
                for container in containers_data:
                    labels = container.get("Labels", {})
                    if labels.get("com.docker.compose.project") == stack_name:
                        stack_containers.append(container["Id"])
                
                if not stack_containers:
                    _LOGGER.warning("No containers found for stack %s", stack_name)
                    return False
                
                _LOGGER.info("Found %d containers in stack %s", len(stack_containers), stack_name)
                
                # Stop each container in the stack
                success_count = 0
                for container_id in stack_containers:
                    try:
                        stop_url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/containers/{container_id}/stop"
                        async with self.session.post(stop_url, headers=self.headers, ssl=False) as stop_resp:
                            if stop_resp.status == 204:
                                success_count += 1
                                _LOGGER.debug("✅ Stopped container %s", container_id)
                            else:
                                _LOGGER.warning("⚠️ Failed to stop container %s: %s", container_id, stop_resp.status)
                    except Exception as e:
                        _LOGGER.warning("⚠️ Error stopping container %s: %s", container_id, e)
                
                _LOGGER.info("✅ Successfully stopped %d/%d containers in stack %s", 
                           success_count, len(stack_containers), stack_name)
                return success_count > 0
                
        except Exception as e:
            _LOGGER.exception("❌ Error stopping stack %s: %s", stack_name, e)
            return False

    async def start_stack(self, endpoint_id, stack_name):
        """Start all containers in a stack."""
        try:
            _LOGGER.info("▶️ Starting stack %s", stack_name)
            
            # Get all containers in the stack
            containers_url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/containers/json?all=1"
            async with self.session.get(containers_url, headers=self.headers, ssl=False) as resp:
                if resp.status != 200:
                    _LOGGER.error("Could not get containers list: %s", resp.status)
                    return False
                
                containers_data = await resp.json()
                stack_containers = []
                
                # Find all containers belonging to this stack
                for container in containers_data:
                    labels = container.get("Labels", {})
                    if labels.get("com.docker.compose.project") == stack_name:
                        stack_containers.append(container["Id"])
                
                if not stack_containers:
                    _LOGGER.warning("No containers found for stack %s", stack_name)
                    return False
                
                _LOGGER.info("Found %d containers in stack %s", len(stack_containers), stack_name)
                
                # Start each container in the stack
                success_count = 0
                for container_id in stack_containers:
                    try:
                        start_url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/containers/{container_id}/start"
                        async with self.session.post(start_url, headers=self.headers, ssl=False) as start_resp:
                            if start_resp.status == 204:
                                success_count += 1
                                _LOGGER.debug("✅ Started container %s", container_id)
                            else:
                                _LOGGER.warning("⚠️ Failed to start container %s: %s", container_id, start_resp.status)
                    except Exception as e:
                        _LOGGER.warning("⚠️ Error starting container %s: %s", container_id, e)
                
                _LOGGER.info("✅ Successfully started %d/%d containers in stack %s", 
                           success_count, len(stack_containers), stack_name)
                return success_count > 0
                
        except Exception as e:
            _LOGGER.exception("❌ Error starting stack %s: %s", stack_name, e)
            return False

    # ---------------------------
    # Added helpers for stack update integration
    # ---------------------------
    def get_headers(self):
        """Return current headers for API requests (used by sub-APIs)."""
        return self.headers

    async def update_stack(self, endpoint_id, stack_name, *, pull_image: bool = True, prune: bool = False, wait_timeout: float = 90.0, wait_interval: float = 2.0):
        """Update a stack by pulling latest images and redeploying the stack compose.
        Returns a result dict from the underlying stack API.
        """
        try:
            from .stack_api import PortainerStackAPI
        except Exception as e:
            _LOGGER.exception("❌ Failed to import PortainerStackAPI: %s", e)
            return {"ok": False, "error": str(e)}

        stack_api = PortainerStackAPI(self.base_url, self, ssl_verify=False, session=self.session)
        try:
            result = await stack_api.update_stack(
                endpoint_id,
                stack_name,
                pull_image=pull_image,
                prune=prune,
                wait_timeout=wait_timeout,
                wait_interval=wait_interval,
            )
            return result
        except Exception as e:
            _LOGGER.exception("❌ Error during stack update for %s: %s", stack_name, e)
            return {"ok": False, "error": str(e)}
