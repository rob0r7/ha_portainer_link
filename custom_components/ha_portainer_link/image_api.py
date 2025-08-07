import logging
import aiohttp
from typing import Optional, Dict, Any

_LOGGER = logging.getLogger(__name__)

class PortainerImageAPI:
    """Handle Portainer image operations."""

    def __init__(self, base_url: str, auth):
        """Initialize image API."""
        self.base_url = base_url
        self.auth = auth

    async def check_image_updates(self, endpoint_id: int, container_id: str) -> bool:
        """Check if a container's image has updates available by actually pulling from registry."""
        try:
            # Get container inspection data
            container_info = await self._get_container_info(endpoint_id, container_id)
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
            async with self.auth.session.get(current_image_url, headers=self.auth.get_headers(), ssl=False) as resp:
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
            async with self.auth.session.post(pull_url, headers=self.auth.get_headers(), params=params, ssl=False) as resp:
                if resp.status == 200:
                    _LOGGER.debug("✅ Successfully pulled image from registry")
                    
                    # Get the newly pulled image digest
                    images_url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/images/json"
                    async with self.auth.session.get(images_url, headers=self.auth.get_headers(), ssl=False) as resp2:
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

    async def pull_image_update(self, endpoint_id: int, container_id: str) -> bool:
        """Pull the latest image for a container."""
        try:
            # Get container inspection data to find the image
            container_info = await self._get_container_info(endpoint_id, container_id)
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
            
            async with self.auth.session.post(url, headers=self.auth.get_headers(), params=params, ssl=False) as resp:
                if resp.status == 200:
                    _LOGGER.info("✅ Successfully pulled image update for container %s (%s)", container_id, image_name)
                    return True
                else:
                    _LOGGER.error("❌ Failed to pull image update for container %s: %s", container_id, resp.status)
                    return False
        except Exception as e:
            _LOGGER.exception("❌ Error pulling image update for container %s: %s", container_id, e)
            return False

    async def get_image_info(self, endpoint_id: int, image_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a Docker image."""
        try:
            url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/images/{image_id}/json"
            async with self.auth.session.get(url, headers=self.auth.get_headers(), ssl=False) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    _LOGGER.debug("Could not get image info for %s: %s", image_id, resp.status)
                    return None
        except Exception as e:
            _LOGGER.exception("Error getting image info for %s: %s", image_id, e)
            return None

    def extract_version_from_image(self, image_data: Dict[str, Any]) -> str:
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

    async def get_available_version(self, endpoint_id: int, image_name: str) -> str:
        """Get the available version from the registry."""
        try:
            _LOGGER.debug("🔍 Checking available version for %s", image_name)
            
            # First, try to get the current image info without pulling
            images_url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/images/json"
            async with self.auth.session.get(images_url, headers=self.auth.get_headers(), ssl=False) as resp:
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
            
            async with self.auth.session.post(pull_url, headers=self.auth.get_headers(), params=params, ssl=False) as resp:
                if resp.status == 200:
                    _LOGGER.debug("✅ Successfully pulled image %s from registry", image_name)
                    
                    # Get the newly pulled image info
                    async with self.auth.session.get(images_url, headers=self.auth.get_headers(), ssl=False) as resp2:
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

    async def _get_container_info(self, endpoint_id: int, container_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed container information including image details."""
        url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/containers/{container_id}/json"
        try:
            async with self.auth.session.get(url, headers=self.auth.get_headers(), ssl=False) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    _LOGGER.error("❌ Failed to get container info: HTTP %s", resp.status)
                    return None
        except Exception as e:
            _LOGGER.exception("❌ Error getting container info: %s", e)
            return None
