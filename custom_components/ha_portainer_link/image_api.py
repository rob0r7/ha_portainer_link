import logging
import aiohttp
from typing import Optional, Dict, Any
import time
from aiohttp.client_exceptions import ClientConnectorCertificateError

_LOGGER = logging.getLogger(__name__)

class PortainerImageAPI:
    """Handle Portainer image operations."""

    def __init__(self, base_url: str, auth, config: Optional[Dict[str, Any]] = None, ssl_verify: bool = True, session=None):
        """Initialize image API."""
        self.base_url = base_url
        self.auth = auth
        self.config = config or {}
        self.ssl_verify = ssl_verify
        self.session = session  # Use shared session from main API
        
        # Initialize rate limiting with fixed values (simplified)
        self._cache_duration = 6 * 3600  # 6 hours in seconds
        self._rate_limit_checks = 50
        self._rate_limit_period = 6 * 3600  # 6 hours in seconds
        
        # Initialize caches and counters
        self._update_cache: Dict[str, tuple] = {}
        self._version_cache: Dict[str, tuple] = {}
        self._last_update_check = time.time()
        self._update_check_count = 0
        self._last_version_check = time.time()
        self._version_check_count = 0

    async def check_image_updates(self, endpoint_id: int, container_id: str) -> bool:
        """Check if a container's image has updates available by comparing local vs registry metadata."""
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
            session = self.session or self.auth.session
            async with session.get(current_image_url, headers=self.auth.get_headers(), ssl=self.ssl_verify) as resp:
                if resp.status != 200:
                    _LOGGER.debug("Could not get current image info: %s", resp.status)
                    return False
                current_image_data = await resp.json()
                # Prefer RepoDigests when available; fall back to Id
                repo_digests = current_image_data.get("RepoDigests") or []
                current_digest = (repo_digests[0] if repo_digests else current_image_data.get("Id", ""))
                current_created = current_image_data.get("Created", "")
            
            _LOGGER.debug("Current image digest: %s, created: %s", 
                         (current_digest.split("@")[-1] if "@" in current_digest else current_digest)[:12] if current_digest else "unknown",
                         current_created[:19] if current_created else "unknown")
            
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
            
            # Try to inspect the image on the registry without pulling
            # This is more efficient and doesn't hit rate limits as hard
            try:
                # Use Docker Hub API for all Docker Hub images (both official and third-party)
                # Official images: library/ubuntu, library/nginx (no slash in display name)
                # Third-party images: interaapps/pastefy, jlesage/firefox (has slash)
                # Custom images: localhost:5000/myapp, registry.company.com/app (not Docker Hub)
                
                # Check if this is a Docker Hub image (not a custom registry)
                if not any(registry in image_name for registry in ["localhost:", "registry.", "harbor.", "gitlab.", "github."]):
                    # This is a Docker Hub image - can use Docker Hub API
                    if ":" in image_name:
                        tag = image_name.split(":")[-1]
                        repo = image_name.split(":")[0]
                    else:
                        tag = "latest"
                        repo = image_name
                    
                    # Handle both official (library/) and third-party (user/) images
                    if repo.startswith("library/"):
                        # Official image: library/ubuntu -> ubuntu
                        clean_repo = repo.replace("library/", "")
                        registry_url = f"https://registry.hub.docker.com/v2/repositories/library/{clean_repo}/tags/{tag}"
                    elif "/" not in repo:
                        # Official image without library/ prefix: mariadb -> library/mariadb
                        registry_url = f"https://registry.hub.docker.com/v2/repositories/library/{repo}/tags/{tag}"
                    else:
                        # Third-party image: interaapps/pastefy -> interaapps/pastefy
                        registry_url = f"https://registry.hub.docker.com/v2/repositories/{repo}/tags/{tag}"
                    
                    _LOGGER.debug("🔍 Checking Docker Hub API: %s", registry_url)
                    
                    # Use aiohttp to check registry metadata
                    async with session.get(registry_url, ssl=False) as registry_resp:
                        if registry_resp.status == 200:
                            registry_data = await registry_resp.json()
                            # Prefer images[0].digest if available, else top-level digest
                            images_list = registry_data.get("images") or []
                            image_digest = None
                            if images_list and isinstance(images_list[0], dict):
                                image_digest = images_list[0].get("digest")
                            if not image_digest:
                                image_digest = registry_data.get("digest", "")
                            if image_digest:
                                short_registry = (image_digest.split(":")[-1])[:12]
                                short_local = (current_digest.split("@")[-1] if "@" in current_digest else current_digest)[:12]
                                if short_registry and short_local and short_registry != short_local:
                                    _LOGGER.debug("✅ New image available for %s (registry: %s, local: %s)", image_name, short_registry, short_local)
                                    self._update_cache[cache_key] = (True, time.time())
                                    return True
                            _LOGGER.debug("✅ Image %s is up to date", image_name)
                            self._update_cache[cache_key] = (False, time.time())
                            return False
                        else:
                            _LOGGER.debug("Could not check Docker Hub for %s: HTTP %s", image_name, registry_resp.status)
                            # Handle specific HTTP status codes for update checks
                            if registry_resp.status == 429:
                                _LOGGER.debug("Rate limited for %s - assuming no update available", image_name)
                                self._update_cache[cache_key] = (False, time.time())
                                return False
                            elif registry_resp.status == 404:
                                _LOGGER.debug("Tag not found for %s - assuming no update available", image_name)
                                self._update_cache[cache_key] = (False, time.time())
                                return False
                            elif registry_resp.status == 403:
                                _LOGGER.debug("Access denied for %s - assuming no update available", image_name)
                                self._update_cache[cache_key] = (False, time.time())
                                return False
                            else:
                                _LOGGER.debug("HTTP %s error for %s - assuming no update available", registry_resp.status, image_name)
                                self._update_cache[cache_key] = (False, time.time())
                                return False
                else:
                    # Custom registry image - try to use Portainer's built-in update check
                    # This is more reliable than trying to parse custom registry APIs
                    _LOGGER.debug("Custom registry image %s - using Portainer's update detection", image_name)
                    
                    # For custom registry images, we'll use a more conservative approach
                    # Check if the container is running and if the image is recent
                    if current_created:
                        try:
                            from datetime import datetime
                            created_time = datetime.fromisoformat(current_created.replace('Z', '+00:00'))
                            current_age = (datetime.now(created_time.tzinfo) - created_time).days
                            
                            # If image is older than 30 days, suggest checking for updates
                            if current_age > 30:
                                _LOGGER.debug("Image %s is %d days old - suggesting update check", image_name, current_age)
                                self._update_cache[cache_key] = (True, time.time())
                                return True
                            else:
                                _LOGGER.debug("Image %s is %d days old - likely up to date", image_name, current_age)
                                self._update_cache[cache_key] = (False, time.time())
                                return False
                        except Exception as parse_e:
                            _LOGGER.debug("Could not parse image creation time: %s", parse_e)
                    
                    # Default to no update available for custom registry images
                    self._update_cache[cache_key] = (False, time.time())
                    return False
                    
            except Exception as e:
                _LOGGER.debug("Error checking registry for %s: %s", image_name, e)
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
            
            session = self.session or self.auth.session
            async with session.post(pull_url, params=params, headers=self.auth.get_headers(), ssl=self.ssl_verify) as resp:
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
            
            # Try with current SSL setting first
            try:
                session = self.session or self.auth.session
                async with session.get(image_url, headers=self.auth.get_headers(), ssl=self.ssl_verify) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    else:
                        _LOGGER.error("❌ Failed to get image info: HTTP %s", resp.status)
                        return None
            except ClientConnectorCertificateError as e:
                _LOGGER.info("🔧 SSL certificate error, retrying with SSL disabled: %s", e)
                # Retry with SSL disabled
                try:
                    async with session.get(image_url, headers=self.auth.get_headers(), ssl=False) as resp:
                        if resp.status == 200:
                            _LOGGER.info("✅ Successfully connected with SSL disabled")
                            # Update SSL setting for future calls
                            self.ssl_verify = False
                            return await resp.json()
                        else:
                            _LOGGER.error("❌ Failed to get image info: HTTP %s", resp.status)
                            return None
                except Exception as retry_e:
                    _LOGGER.exception("❌ Error getting image info with SSL disabled: %s", retry_e)
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
        """Get the available version from the registry without pulling images."""
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
            
            # Try to get version from registry metadata without pulling
            try:
                session = self.session or self.auth.session
                
                # Use Docker Hub API for all Docker Hub images (both official and third-party)
                # Official images: library/ubuntu, library/nginx (no slash in display name)
                # Third-party images: interaapps/pastefy, jlesage/firefox (has slash)
                # Custom images: localhost:5000/myapp, registry.company.com/app (not Docker Hub)
                
                # Check if this is a Docker Hub image (not a custom registry)
                if not any(registry in image_name for registry in ["localhost:", "registry.", "harbor.", "gitlab.", "github."]):
                    # This is a Docker Hub image - can use Docker Hub API
                    if ":" in image_name:
                        tag = image_name.split(":")[-1]
                        repo = image_name.split(":")[0]
                    else:
                        tag = "latest"
                        repo = image_name
                    
                    # Handle both official (library/) and third-party (user/) images
                    if repo.startswith("library/"):
                        # Official image: library/ubuntu -> ubuntu
                        clean_repo = repo.replace("library/", "")
                        registry_url = f"https://registry.hub.docker.com/v2/repositories/library/{clean_repo}/tags/{tag}"
                    elif "/" not in repo:
                        # Official image without library/ prefix: mariadb -> library/mariadb
                        # Docker Hub automatically adds library/ to official images
                        registry_url = f"https://registry.hub.docker.com/v2/repositories/library/{repo}/tags/{tag}"
                    else:
                        # Third-party image: interaapps/pastefy -> interaapps/pastefy
                        registry_url = f"https://registry.hub.docker.com/v2/repositories/{repo}/tags/{tag}"
                    
                    _LOGGER.debug("🔍 Getting version from Docker Hub API: %s", registry_url)
                    
                    async with session.get(registry_url, ssl=False) as registry_resp:
                        if registry_resp.status == 200:
                            registry_data = await registry_resp.json()
                            
                            # Try to get version from various sources
                            version = None
                            
                            # Check for version in image labels
                            if "images" in registry_data and registry_data["images"]:
                                # Get the first image's labels
                                first_image = registry_data["images"][0]
                                labels = first_image.get("labels", {})
                                
                                version_labels = [
                                    "org.opencontainers.image.version",
                                    "version",
                                    "VERSION",
                                    "app.version",
                                    "build.version"
                                ]
                                
                                for label in version_labels:
                                    if label in labels and labels[label]:
                                        version = labels[label]
                                        break
                            
                            # If no version from labels, use tag or creation date
                            if not version:
                                if tag and tag != "latest":
                                    version = tag
                                else:
                                    # Try to get creation date
                                    if "images" in registry_data and registry_data["images"]:
                                        created = registry_data["images"][0].get("created", "")
                                        if created:
                                            try:
                                                from datetime import datetime
                                                dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                                                version = dt.strftime("%Y.%m.%d")
                                            except:
                                                version = "latest"
                                        else:
                                            version = "latest"
                                    else:
                                        version = "latest"
                            
                            _LOGGER.debug("✅ Got version %s for %s from Docker Hub", version, image_name)
                            self._version_cache[image_name] = (version, time.time())
                            return version
                        else:
                            _LOGGER.debug("Could not get Docker Hub info for %s: HTTP %s", image_name, registry_resp.status)
                            # Handle specific HTTP status codes
                            if registry_resp.status == 429:
                                return "unknown (rate limited)"
                            elif registry_resp.status == 404:
                                return "unknown (tag not found)"
                            elif registry_resp.status == 403:
                                return "unknown (access denied)"
                            else:
                                return f"unknown (HTTP {registry_resp.status})"
                else:
                    # Custom registry image - try to extract version from image name
                    _LOGGER.debug("Custom registry image %s - extracting version from name", image_name)
                    
                    if ":" in image_name:
                        version = image_name.split(":")[-1]
                        if version and version != "latest":
                            _LOGGER.debug("✅ Got version %s for %s from image name", version, image_name)
                            self._version_cache[image_name] = (version, time.time())
                            return version
                    
                    # For custom registry images, we'll use a more descriptive fallback
                    version = "custom registry"
                    self._version_cache[image_name] = (version, time.time())
                    return version
                    
            except Exception as e:
                _LOGGER.debug("Error getting registry version for %s: %s", image_name, e)
            
            # Fallback: extract version from image name
            if ":" in image_name:
                version = image_name.split(":")[-1]
                if version and version != "latest":
                    _LOGGER.debug("✅ Got version %s for %s from image name (fallback)", version, image_name)
                    self._version_cache[image_name] = (version, time.time())
                    return version
            
            # Final fallback
            version = "latest"
            _LOGGER.debug("✅ Using fallback version %s for %s", version, image_name)
            self._version_cache[image_name] = (version, time.time())
            return version
                
        except Exception as e:
            _LOGGER.exception("❌ Error getting available version for image %s: %s", image_name, e)
            return "unknown"

    async def get_current_digest(self, endpoint_id: int, container_id: str) -> str:
        """Get the current image digest for a container."""
        try:
            # Get container inspection data
            container_info = await self._get_container_info(endpoint_id, container_id)
            if not container_info:
                _LOGGER.debug("No container info found for %s", container_id)
                return "unknown"
            
            # Get current image ID
            current_image_id = container_info.get("Image")
            if not current_image_id:
                _LOGGER.debug("No current image ID found for container %s", container_id)
                return "unknown"
            
            # Get current image details
            current_image_url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/images/{current_image_id}/json"
            session = self.session or self.auth.session
            async with session.get(current_image_url, headers=self.auth.get_headers(), ssl=self.ssl_verify) as resp:
                if resp.status != 200:
                    _LOGGER.debug("Could not get current image info: %s", resp.status)
                    return "unknown"
                current_image_data = await resp.json()
                # Prefer RepoDigests when available; fall back to Id
                repo_digests = current_image_data.get("RepoDigests") or []
                digest = (repo_digests[0] if repo_digests else current_image_data.get("Id", ""))
                if digest:
                    short = (digest.split("@")[-1] if "@" in digest else digest).split(":")[-1][:12]
                    return short
                else:
                    return "unknown"
                    
        except Exception as e:
            _LOGGER.exception("❌ Error getting current digest for container %s: %s", container_id, e)
            return "unknown"

    async def get_available_digest(self, endpoint_id: int, container_id: str) -> str:
        """Get the available image digest from registry for a container."""
        try:
            # Get container inspection data
            container_info = await self._get_container_info(endpoint_id, container_id)
            if not container_info:
                _LOGGER.debug("No container info found for %s", container_id)
                return "unknown"
            
            # Extract image information
            image_name = container_info.get("Config", {}).get("Image")
            if not image_name:
                _LOGGER.debug("No image name found for container %s", container_id)
                return "unknown"
            
            _LOGGER.debug("🔍 Getting available digest for container %s with image: %s", container_id, image_name)
            
            # Try to get digest from registry metadata without pulling
            try:
                session = self.session or self.auth.session
                
                # Use Docker Hub API for all Docker Hub images (both official and third-party)
                # Official images: library/ubuntu, library/nginx (no slash in display name)
                # Third-party images: interaapps/pastefy, jlesage/firefox (has slash)
                # Custom images: localhost:5000/myapp, registry.company.com/app (not Docker Hub)
                
                # Check if this is a Docker Hub image (not a custom registry)
                if not any(registry in image_name for registry in ["localhost:", "registry.", "harbor.", "gitlab.", "github."]):
                    # This is a Docker Hub image - can use Docker Hub API
                    if ":" in image_name:
                        tag = image_name.split(":")[-1]
                        repo = image_name.split(":")[0]
                    else:
                        tag = "latest"
                        repo = image_name
                    
                    # Handle both official (library/) and third-party (user/) images
                    if repo.startswith("library/"):
                        # Official image: library/ubuntu -> ubuntu
                        clean_repo = repo.replace("library/", "")
                        registry_url = f"https://registry.hub.docker.com/v2/repositories/library/{clean_repo}/tags/{tag}"
                    elif "/" not in repo:
                        # Official image without library/ prefix: mariadb -> library/mariadb
                        registry_url = f"https://registry.hub.docker.com/v2/repositories/library/{repo}/tags/{tag}"
                    else:
                        # Third-party image: interaapps/pastefy -> interaapps/pastefy
                        registry_url = f"https://registry.hub.docker.com/v2/repositories/{repo}/tags/{tag}"
                    
                    _LOGGER.debug("🔍 Querying Docker Hub API: %s", registry_url)
                    
                    async with session.get(registry_url, ssl=False) as registry_resp:
                        if registry_resp.status == 200:
                            registry_data = await registry_resp.json()
                            # Prefer images[0].digest if available, else top-level digest
                            images_list = registry_data.get("images") or []
                            image_digest = None
                            if images_list and isinstance(images_list[0], dict):
                                image_digest = images_list[0].get("digest")
                            if not image_digest:
                                image_digest = registry_data.get("digest", "")
                            if image_digest:
                                short = (image_digest.split(":")[-1])[:12]
                                _LOGGER.debug("✅ Got available digest %s for %s from Docker Hub", short, image_name)
                                return short
                            else:
                                _LOGGER.debug("No digest found in registry data for %s", image_name)
                                return "unknown (no digest)"
                        else:
                            _LOGGER.debug("Could not get Docker Hub info for %s: HTTP %s", image_name, registry_resp.status)
                            # Handle specific HTTP status codes
                            if registry_resp.status == 429:
                                return "unknown (rate limited)"
                            elif registry_resp.status == 404:
                                return "unknown (tag not found)"
                            elif registry_resp.status == 403:
                                return "unknown (access denied)"
                            else:
                                return f"unknown (HTTP {registry_resp.status})"
                else:
                    # Custom registry image - can't easily get digest without pulling
                    _LOGGER.debug("Custom registry image %s - cannot get digest without pulling", image_name)
                    return "unknown (custom registry)"
                    
            except Exception as e:
                _LOGGER.debug("Error checking registry for %s: %s", image_name, e)
                return "unknown (registry error)"
                
        except Exception as e:
            _LOGGER.exception("❌ Error getting available digest for container %s: %s", container_id, e)
            return "unknown"

    async def _get_container_info(self, endpoint_id: int, container_id: str) -> Optional[Dict[str, Any]]:
        """Get container inspection data."""
        try:
            container_url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/containers/{container_id}/json"
            
            # Try with current SSL setting first
            try:
                session = self.session or self.auth.session
                async with session.get(container_url, headers=self.auth.get_headers(), ssl=self.ssl_verify) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    else:
                        _LOGGER.error("❌ Failed to get container info: HTTP %s", resp.status)
                        return None
            except ClientConnectorCertificateError as e:
                _LOGGER.info("🔧 SSL certificate error, retrying with SSL disabled: %s", e)
                # Retry with SSL disabled
                try:
                    async with session.get(container_url, headers=self.auth.get_headers(), ssl=False) as resp:
                        if resp.status == 200:
                            _LOGGER.info("✅ Successfully connected with SSL disabled")
                            # Update SSL setting for future calls
                            self.ssl_verify = False
                            return await resp.json()
                        else:
                            _LOGGER.error("❌ Failed to get container info: HTTP %s", resp.status)
                            return None
                except Exception as retry_e:
                    _LOGGER.exception("❌ Error getting container info with SSL disabled: %s", retry_e)
                    return None
                    
        except Exception as e:
            _LOGGER.exception("❌ Error getting container info: %s", e)
            return None
