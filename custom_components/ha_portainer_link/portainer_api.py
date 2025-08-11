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
                                    _LOGGER.debug("Pulled image digest: %s", new_digest[:12] if new_digest else "unknown")
                                    return new_digest != current_digest
                        return False
                else:
                    _LOGGER.debug("Could not pull image %s: HTTP %s", image_name, resp.status)
                    return False
        except Exception as e:
            _LOGGER.exception("❌ Error checking updates for container %s: %s", container_id, e)
            return False

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
            
            # First, try to get the current image info without pulling
            images_url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/images/json"
            async with self.session.get(images_url, headers=self.headers, ssl=False) as resp:
                if resp.status == 200:
                    images_data = await resp.json()
                    # Find the image with the same name
                    for image in images_data:
                        repo_tags = image.get("RepoTags", [])
                        if image_name in repo_tags:
                            version = self.extract_version_from_image(image)
                            _LOGGER.debug("✅ Found existing image %s: %s", image_name, version)
                            return version
            
            # If not found locally, try to pull from registry
            _LOGGER.debug("🔄 Image %s not found locally, pulling from registry", image_name)
            pull_url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/images/create"
            params = {"fromImage": image_name}
            
            async with self.session.post(pull_url, headers=self.headers, params=params, ssl=False) as resp:
                if resp.status == 200:
                    _LOGGER.debug("✅ Successfully pulled image %s from registry", image_name)
                    
                    # Get the newly pulled image info
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
                else:
                    _LOGGER.warning("⚠️ Failed to pull image %s: HTTP %s", image_name, resp.status)
                    return f"unknown (HTTP {resp.status})"
        except Exception as e:
            _LOGGER.exception("❌ Error getting available version for image %s: %s", image_name, e)
            return "unknown"

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

    async def get_current_digest(self, endpoint_id, container_id):
        """Wrapper delegating to image API for current digest."""
        try:
            from .image_api import PortainerImageAPI
            image_api = PortainerImageAPI(self.base_url, self, ssl_verify=False, session=self.session)
            return await image_api.get_current_digest(endpoint_id, container_id)
        except Exception as e:
            _LOGGER.exception("❌ Error in get_current_digest: %s", e)
            return "unknown"

    async def get_available_digest(self, endpoint_id, container_id):
        """Wrapper delegating to image API for available digest."""
        try:
            from .image_api import PortainerImageAPI
            image_api = PortainerImageAPI(self.base_url, self, ssl_verify=False, session=self.session)
            return await image_api.get_available_digest(endpoint_id, container_id)
        except Exception as e:
            _LOGGER.exception("❌ Error in get_available_digest: %s", e)
            return "unknown"
