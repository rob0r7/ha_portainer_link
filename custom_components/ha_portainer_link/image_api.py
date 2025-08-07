import logging
import aiohttp
from typing import Optional, Dict, Any
import time

from .const import (
    CONF_CACHE_DURATION, CONF_RATE_LIMIT_CHECKS, CONF_RATE_LIMIT_PERIOD,
    DEFAULT_CACHE_DURATION, DEFAULT_RATE_LIMIT_CHECKS, DEFAULT_RATE_LIMIT_PERIOD
)

_LOGGER = logging.getLogger(__name__)

class PortainerImageAPI:
    """Handle Portainer image operations."""

    def __init__(self, base_url: str, auth, config: Optional[Dict[str, Any]] = None, ssl_verify: bool = True):
        """Initialize image API."""
        self.base_url = base_url
        self.auth = auth
        self.config = config or {}
        self.ssl_verify = ssl_verify
        
        # Initialize rate limiting with configurable values
        self._cache_duration = self.config.get(CONF_CACHE_DURATION, DEFAULT_CACHE_DURATION) * 3600  # Convert to seconds
        self._rate_limit_checks = self.config.get(CONF_RATE_LIMIT_CHECKS, DEFAULT_RATE_LIMIT_CHECKS)
        self._rate_limit_period = self.config.get(CONF_RATE_LIMIT_PERIOD, DEFAULT_RATE_LIMIT_PERIOD) * 3600  # Convert to seconds
        
        # Initialize caches and counters
        self._update_cache: Dict[str, tuple] = {}
        self._version_cache: Dict[str, tuple] = {}
        self._last_update_check = time.time()
        self._update_check_count = 0
        self._last_version_check = time.time()
        self._version_check_count = 0

    async def check_image_updates(self, endpoint_id: int, container_id: str) -> bool:
        """Check if a container's image has updates available with configurable rate limiting."""
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
            async with self.auth.session.get(current_image_url, headers=self.auth.get_headers(), ssl=self.ssl_verify) as resp:
                if resp.status != 200:
                    _LOGGER.debug("Could not get current image info: %s", resp.status)
                    return False
                current_image_data = await resp.json()
                current_digest = current_image_data.get("Id", "")
            
            _LOGGER.debug("Current image digest: %s", current_digest[:12] if current_digest else "unknown")
            
            # Check if we have a cached result for this image
            cache_key = f"{image_name}_{current_digest[:12]}"
            if cache_key in self._update_cache:
                cached_result, cache_time = self._update_cache[cache_key]
                # Use configurable cache duration
                if (time.time() - cache_time) < self._cache_duration:
                    _LOGGER.debug("Using cached update check result for %s: %s", image_name, cached_result)
                    return cached_result
            
            # Check if we've made too many API calls recently (rate limiting)
            current_time = time.time()
            # Reset counter if rate limit period has passed
            if (current_time - self._last_update_check) > self._rate_limit_period:
                self._update_check_count = 0
                self._last_update_check = current_time
            
            # Check against configurable rate limit
            if self._update_check_count >= self._rate_limit_checks:
                _LOGGER.debug("Rate limit reached for update checks (%d/%d), using cached result for %s", 
                             self._update_check_count, self._rate_limit_checks, image_name)
                # Return cached result or False if no cache
                if cache_key in self._update_cache:
                    return self._update_cache[cache_key][0]
                return False
            
            # Increment counter
            self._update_check_count += 1
            
            # Try to pull the latest image from registry (this is the rate-limited operation)
            pull_url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/images/create"
            params = {"fromImage": image_name}
            
            try:
                async with self.auth.session.post(pull_url, params=params, headers=self.auth.get_headers(), ssl=self.ssl_verify) as resp:
                    if resp.status == 200:
                        # Successfully pulled new image
                        _LOGGER.debug("✅ New image available for %s", image_name)
                        self._update_cache[cache_key] = (True, time.time())
                        return True
                    elif resp.status == 304:
                        # Image is up to date
                        _LOGGER.debug("✅ Image %s is up to date", image_name)
                        self._update_cache[cache_key] = (False, time.time())
                        return False
                    else:
                        _LOGGER.debug("Could not check image updates: HTTP %s", resp.status)
                        # Cache the failure for a shorter time
                        self._update_cache[cache_key] = (False, time.time())
                        return False
            except Exception as e:
                _LOGGER.debug("Error checking image updates for %s: %s", image_name, e)
                # Cache the failure for a shorter time
                self._update_cache[cache_key] = (False, time.time())
                return False
                
        except Exception as e:
            _LOGGER.exception("❌ Error checking image updates for container %s: %s", container_id, e)
            return False

    async def pull_image_update(self, endpoint_id: int, container_id: str) -> bool:
        """Pull the latest image for a container."""
        try:
            # Get container inspection data
            container_info = await self._get_container_info(endpoint_id, container_id)
            if not container_info:
                _LOGGER.error("No container info found for %s", container_id)
                return False
            
            # Extract image information
            image_name = container_info.get("Config", {}).get("Image")
            if not image_name:
                _LOGGER.error("No image name found for container %s", container_id)
                return False
            
            _LOGGER.info("🔄 Pulling latest image for container %s: %s", container_id, image_name)
            
            # Pull the latest image
            pull_url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/images/create"
            params = {"fromImage": image_name}
            
            async with self.auth.session.post(pull_url, params=params, headers=self.auth.get_headers(), ssl=self.ssl_verify) as resp:
                if resp.status == 200:
                    _LOGGER.info("✅ Successfully pulled latest image for %s", image_name)
                    return True
                else:
                    _LOGGER.error("❌ Failed to pull image %s: HTTP %s", image_name, resp.status)
                    return False
                    
        except Exception as e:
            _LOGGER.exception("❌ Error pulling image update for container %s: %s", container_id, e)
            return False

    async def get_image_info(self, endpoint_id: int, image_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a Docker image."""
        try:
            image_url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/images/{image_id}/json"
            async with self.auth.session.get(image_url, headers=self.auth.get_headers(), ssl=self.ssl_verify) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    _LOGGER.error("❌ Failed to get image info: HTTP %s", resp.status)
                    return None
        except Exception as e:
            _LOGGER.exception("❌ Error getting image info: %s", e)
            return None

    def extract_version_from_image(self, image_data: Dict[str, Any]) -> str:
        """Extract version information from image data."""
        try:
            if not image_data:
                return "unknown"
            
            # Try to get version from image tags
            repo_tags = image_data.get("RepoTags", [])
            if repo_tags:
                # Look for version tags (e.g., "latest", "v1.2.3", "2023.12.01")
                for tag in repo_tags:
                    if ":" in tag:
                        version = tag.split(":")[-1]
                        if version and version != "latest":
                            return version
            
            # Try to get version from image labels
            labels = image_data.get("Labels", {})
            version_labels = [
                "org.opencontainers.image.version",
                "version",
                "VERSION",
                "app.version",
                "build.version"
            ]
            
            for label in version_labels:
                if label in labels:
                    version = labels[label]
                    if version:
                        return version
            
            # Try to get version from creation date
            created = image_data.get("Created", "")
            if created:
                # Extract date from ISO format
                try:
                    from datetime import datetime
                    dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    return dt.strftime("%Y.%m.%d")
                except:
                    pass
            
            # Fallback to image ID
            image_id = image_data.get("Id", "")
            if image_id:
                return image_id[:12]  # Return first 12 characters of image ID
            
            return "unknown"
            
        except Exception as e:
            _LOGGER.exception("❌ Error extracting version from image: %s", e)
            return "unknown"

    async def get_available_version(self, endpoint_id: int, image_name: str) -> str:
        """Get the available version from the registry with configurable rate limiting."""
        try:
            _LOGGER.debug("🔍 Getting available version for image: %s", image_name)
            
            # Check if we have a cached result for this image
            if image_name in self._version_cache:
                cached_result, cache_time = self._version_cache[image_name]
                # Use configurable cache duration
                if (time.time() - cache_time) < self._cache_duration:
                    _LOGGER.debug("Using cached version result for %s: %s", image_name, cached_result)
                    return cached_result
            
            # Check if we've made too many API calls recently (rate limiting)
            current_time = time.time()
            # Reset counter if rate limit period has passed
            if (current_time - self._last_version_check) > self._rate_limit_period:
                self._version_check_count = 0
                self._last_version_check = current_time
            
            # Check against configurable rate limit
            if self._version_check_count >= self._rate_limit_checks:
                _LOGGER.debug("Rate limit reached for version checks (%d/%d), using cached result for %s", 
                             self._version_check_count, self._rate_limit_checks, image_name)
                # Return cached result or "unknown (rate limited)" if no cache
                if image_name in self._version_cache:
                    return self._version_cache[image_name][0]
                return "unknown (rate limited)"
            
            # Increment counter
            self._version_check_count += 1
            
            # Try to pull the latest image to get version info
            pull_url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/images/create"
            params = {"fromImage": image_name}
            
            try:
                async with self.auth.session.post(pull_url, params=params, headers=self.auth.get_headers(), ssl=self.ssl_verify) as resp:
                    if resp.status == 200:
                        # Successfully pulled new image, get its info
                        image_id = resp.headers.get("X-Docker-Content-Digest", "")
                        if image_id:
                            # Get image details
                            image_info = await self.get_image_info(endpoint_id, image_id)
                            if image_info:
                                version = self.extract_version_from_image(image_info)
                                self._version_cache[image_name] = (version, time.time())
                                return version
                        
                        # Fallback: extract version from image name
                        if ":" in image_name:
                            version = image_name.split(":")[-1]
                            if version and version != "latest":
                                self._version_cache[image_name] = (version, time.time())
                                return version
                        
                        # Default fallback
                        version = "latest"
                        self._version_cache[image_name] = (version, time.time())
                        return version
                        
                    elif resp.status == 304:
                        # Image is up to date, get current version
                        # This is a bit tricky since we don't have the current image ID
                        # We'll use the image name as fallback
                        if ":" in image_name:
                            version = image_name.split(":")[-1]
                            if version and version != "latest":
                                self._version_cache[image_name] = (version, time.time())
                                return version
                        
                        version = "current"
                        self._version_cache[image_name] = (version, time.time())
                        return version
                        
                    else:
                        _LOGGER.debug("Could not get available version: HTTP %s", resp.status)
                        version = "unknown"
                        self._version_cache[image_name] = (version, time.time())
                        return version
                        
            except Exception as e:
                _LOGGER.debug("Error getting available version for %s: %s", image_name, e)
                version = "unknown"
                self._version_cache[image_name] = (version, time.time())
                return version
                
        except Exception as e:
            _LOGGER.exception("❌ Error getting available version for image %s: %s", image_name, e)
            return "unknown"

    async def _get_container_info(self, endpoint_id: int, container_id: str) -> Optional[Dict[str, Any]]:
        """Get container inspection data."""
        try:
            container_url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/containers/{container_id}/json"
            async with self.auth.session.get(container_url, headers=self.auth.get_headers(), ssl=self.ssl_verify) as resp:
                if resp.status == 200:
                    return await resp.json()
                else:
                    _LOGGER.error("❌ Failed to get container info: HTTP %s", resp.status)
                    return None
        except Exception as e:
            _LOGGER.exception("❌ Error getting container info: %s", e)
            return None
