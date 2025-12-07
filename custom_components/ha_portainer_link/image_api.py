import logging
import aiohttp
from typing import Optional, Dict, Any, Tuple
import time
from aiohttp.client_exceptions import ClientConnectorCertificateError
import re
from urllib.parse import urlparse, parse_qs

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
        self._digest_cache: Dict[str, tuple] = {}
        self._last_update_check = time.time()
        self._update_check_count = 0
        self._last_version_check = time.time()
        self._version_check_count = 0

    # ---------------------
    # Generic OCI Registry helpers
    # ---------------------
    def _parse_image_ref(self, image: str) -> Tuple[str, str, str]:
        """Return (registry, repository, tag). Defaults: docker.io, library namespace, tag=latest.
        Examples:
        - nginx -> (registry-1.docker.io, library/nginx, latest)
        - user/app:1.2 -> (registry-1.docker.io, user/app, 1.2)
        - ghcr.io/org/app:main -> (ghcr.io, org/app, main)
        - registry.example.com/ns/app -> (registry.example.com, ns/app, latest)
        - localhost:5000/app:tag -> (localhost:5000, app, tag)
        """
        ref = image
        tag = "latest"
        # Digest form not handled for tag parsing; treat after
        if "@" in ref:
            ref, _ = ref.split("@", 1)
        if ":" in ref and "/" in ref.split(":")[0]:
            # This colon is part of registry (host:port), not tag
            pass
        elif ":" in ref:
            ref, tag = ref.rsplit(":", 1)
        parts = ref.split("/")
        if len(parts) == 1:
            # docker hub library image
            registry = "registry-1.docker.io"
            repository = f"library/{parts[0]}"
        else:
            first = parts[0]
            if "." in first or ":" in first or first == "localhost":
                registry = first
                repository = "/".join(parts[1:])
            else:
                registry = "registry-1.docker.io"
                repository = "/".join(parts)
        return registry, repository, tag

    async def _request_registry(self, method: str, url: str, *, headers: Optional[Dict[str, str]] = None, token_url: Optional[str] = None, token_params: Optional[Dict[str, str]] = None) -> aiohttp.ClientResponse:
        """Perform a registry request, handling SSL fallback; token acquisition done by caller."""
        session = self.session or self.auth.session
        try:
            return await session.request(method, url, headers=headers, ssl=self.ssl_verify)
        except ClientConnectorCertificateError as e:
            _LOGGER.info("🔧 SSL certificate error (registry), retrying with SSL disabled: %s", e)
            self.ssl_verify = False
            return await session.request(method, url, headers=headers, ssl=False)

    def _build_accept_headers(self) -> Dict[str, str]:
        return {
            "Accept": ", ".join([
                "application/vnd.docker.distribution.manifest.v2+json",
                "application/vnd.oci.image.manifest.v1+json",
                "application/vnd.oci.image.index.v1+json",
                "application/vnd.docker.distribution.manifest.list.v2+json",
            ])
        }

    async def _get_registry_auth_token(self, authenticate_header: str) -> Optional[str]:
        """Parse WWW-Authenticate header and fetch a Bearer token."""
        try:
            # Example: Bearer realm="https://auth.docker.io/token",service="registry.docker.io",scope="repository:library/nginx:pull"
            if not authenticate_header or "Bearer" not in authenticate_header:
                return None
            # Extract key="value" pairs
            parts = dict(re.findall(r'(\w+)="([^"]+)"', authenticate_header))
            realm = parts.get("realm")
            service = parts.get("service")
            scope = parts.get("scope")
            if not realm:
                return None
            params = {}
            if service:
                params["service"] = service
            if scope:
                params["scope"] = scope
            session = self.session or self.auth.session
            async with session.get(realm, params=params, ssl=self.ssl_verify) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("token") or data.get("access_token")
                # SSL fallback
                if isinstance(resp, aiohttp.ClientResponse) and resp.status in (401, 403):
                    return None
        except ClientConnectorCertificateError:
            try:
                session = self.session or self.auth.session
                async with session.get(realm, params=params, ssl=False) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        return data.get("token") or data.get("access_token")
            except Exception:
                return None
        except Exception:
            return None
        return None

    async def _get_remote_manifest_digest(self, image_name: str) -> Optional[str]:
        """Fetch manifest digest via OCI v2 API for a given image ref. Returns sha256:..."""
        try:
            registry, repo, tag = self._parse_image_ref(image_name)
            # Special-case docker hub legacy host mapping
            if registry in ("docker.io", "index.docker.io"):
                registry = "registry-1.docker.io"
            url = f"https://{registry}/v2/{repo}/manifests/{tag}"
            headers = self._build_accept_headers()
            # Attempt request without auth first
            resp = await self._request_registry("GET", url, headers=headers)
            async with resp:
                if resp.status == 200:
                    digest = resp.headers.get("Docker-Content-Digest")
                    if not digest:
                        try:
                            data = await resp.json()
                            digest = (data.get("config", {}) or {}).get("digest")
                        except Exception:
                            digest = None
                    return digest
                if resp.status == 401:
                    www = resp.headers.get("WWW-Authenticate") or resp.headers.get("Www-Authenticate")
                    token = await self._get_registry_auth_token(www)
                    if token:
                        auth_headers = dict(headers)
                        auth_headers["Authorization"] = f"Bearer {token}"
                        resp2 = await self._request_registry("GET", url, headers=auth_headers)
                        async with resp2:
                            if resp2.status == 200:
                                digest = resp2.headers.get("Docker-Content-Digest")
                                if not digest:
                                    try:
                                        data = await resp2.json()
                                        digest = (data.get("config", {}) or {}).get("digest")
                                    except Exception:
                                        digest = None
                                return digest
                            _LOGGER.debug("Registry GET failed after token: HTTP %s for %s", resp2.status, image_name)
                _LOGGER.debug("Registry GET failed: HTTP %s for %s", resp.status, image_name)
            return None
        except Exception as e:
            _LOGGER.debug("Failed to fetch remote manifest for %s: %s", image_name, e)
            return None

    # ---------------------
    # Public features
    # ---------------------
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
            cache_key = f"{image_name}_{(current_digest or '')[:12]}"
            if cache_key in self._update_cache:
                cached_result, cache_time = self._update_cache[cache_key]
                # Use configurable cache duration
                if (time.time() - cache_time) < self._cache_duration:
                    _LOGGER.debug("Using cached update check result for %s: %s", image_name, cached_result)
                    return cached_result
            
            # Rate limiting
            current_time = time.time()
            if (current_time - self._last_update_check) > self._rate_limit_period:
                self._update_check_count = 0
                self._last_update_check = current_time
            if self._update_check_count >= self._rate_limit_checks:
                _LOGGER.debug("Rate limit reached for update checks (%d/%d), using cached result for %s", 
                             self._update_check_count, self._rate_limit_checks, image_name)
                if cache_key in self._update_cache:
                    return self._update_cache[cache_key][0]
                return False
            self._update_check_count += 1

            # Primary path: generic OCI v2 manifest digest fetch
            remote_digest = await self._get_remote_manifest_digest(image_name)
            if remote_digest:
                short_registry = (remote_digest.split(":")[-1])[:12]
                short_local = (current_digest.split("@")[-1] if "@" in current_digest else current_digest).split(":")[-1][:12]
                if short_registry and short_local and short_registry != short_local:
                    _LOGGER.debug("✅ New image available for %s (registry: %s, local: %s)", image_name, short_registry, short_local)
                    self._update_cache[cache_key] = (True, time.time())
                    return True
                _LOGGER.debug("✅ Image %s is up to date (digest match)", image_name)
                self._update_cache[cache_key] = (False, time.time())
                return False

            # Fallback: Docker Hub HTTP API if applicable
            try:
                # Check if this is a Docker Hub image (not a custom registry)
                if not any(registry in image_name for registry in ["localhost:", "registry.", "harbor.", "gitlab.", "github.", "ghcr.io", "quay.io", "gcr.io", "azurecr.io", "ecr."]):
                    if ":" in image_name:
                        tag = image_name.split(":")[-1]
                        repo = image_name.split(":")[0]
                    else:
                        tag = "latest"
                        repo = image_name
                    if repo.startswith("library/"):
                        clean_repo = repo.replace("library/", "")
                        registry_url = f"https://registry.hub.docker.com/v2/repositories/library/{clean_repo}/tags/{tag}"
                    elif "/" not in repo:
                        registry_url = f"https://registry.hub.docker.com/v2/repositories/library/{repo}/tags/{tag}"
                    else:
                        registry_url = f"https://registry.hub.docker.com/v2/repositories/{repo}/tags/{tag}"
                    _LOGGER.debug("🔍 Checking Docker Hub API: %s", registry_url)
                    async with session.get(registry_url, ssl=False) as registry_resp:
                        if registry_resp.status == 200:
                            registry_data = await registry_resp.json()
                            images_list = registry_data.get("images") or []
                            image_digest = None
                            if images_list and isinstance(images_list[0], dict):
                                image_digest = images_list[0].get("digest")
                            if not image_digest:
                                image_digest = registry_data.get("digest", "")
                            if image_digest:
                                short_registry = (image_digest.split(":")[-1])[:12]
                                short_local = (current_digest.split("@")[-1] if "@" in current_digest else current_digest).split(":")[-1][:12]
                                if short_registry and short_local and short_registry != short_local:
                                    _LOGGER.debug("✅ New image available for %s (registry: %s, local: %s)", image_name, short_registry, short_local)
                                    self._update_cache[cache_key] = (True, time.time())
                                    return True
                            _LOGGER.debug("✅ Image %s is up to date", image_name)
                            self._update_cache[cache_key] = (False, time.time())
                            return False
                        else:
                            _LOGGER.debug("Docker Hub API fallback failed HTTP %s for %s", registry_resp.status, image_name)
            except Exception as e:
                _LOGGER.debug("Docker Hub fallback error for %s: %s", image_name, e)

            # Last-resort heuristic for unknown/private registries: age-based hint
            if current_created:
                try:
                    from datetime import datetime
                    created_time = datetime.fromisoformat(current_created.replace('Z', '+00:00'))
                    current_age = (datetime.now(created_time.tzinfo) - created_time).days
                    if current_age > 30:
                        _LOGGER.debug("Image %s is %d days old - suggesting update check", image_name, current_age)
                        self._update_cache[cache_key] = (True, time.time())
                        return True
                except Exception:
                    pass
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
            
            # Cache
            if image_name in self._version_cache:
                cached_result, cache_time = self._version_cache[image_name]
                if (time.time() - cache_time) < self._cache_duration:
                    _LOGGER.debug("Using cached version result for %s: %s", image_name, cached_result)
                    return cached_result
            
            # Rate limit
            current_time = time.time()
            if (current_time - self._last_version_check) > self._rate_limit_period:
                self._version_check_count = 0
                self._last_version_check = current_time
            if self._version_check_count >= self._rate_limit_checks:
                if image_name in self._version_cache:
                    return self._version_cache[image_name][0]
                return "unknown (rate limited)"
            self._version_check_count += 1
            
            # Try: use tag if present (best simple indicator)
            version = None
            if ":" in image_name and "@" not in image_name:
                tag = image_name.split(":")[-1]
                if tag and tag != "latest":
                    version = tag
            
            # If not, try Docker Hub metadata for date/labels
            if not version and not any(registry in image_name for registry in ["localhost:", "registry.", "harbor.", "gitlab.", "github.", "ghcr.io", "quay.io", "gcr.io", "azurecr.io", "ecr."]):
                session = self.session or self.auth.session
                if ":" in image_name:
                    tag = image_name.split(":")[-1]
                    repo = image_name.split(":")[0]
                else:
                    tag = "latest"
                    repo = image_name
                if repo.startswith("library/"):
                    clean_repo = repo.replace("library/", "")
                    registry_url = f"https://registry.hub.docker.com/v2/repositories/library/{clean_repo}/tags/{tag}"
                elif "/" not in repo:
                    registry_url = f"https://registry.hub.docker.com/v2/repositories/library/{repo}/tags/{tag}"
                else:
                    registry_url = f"https://registry.hub.docker.com/v2/repositories/{repo}/tags/{tag}"
                _LOGGER.debug("🔍 Getting version from Docker Hub API: %s", registry_url)
                async with session.get(registry_url, ssl=False) as registry_resp:
                    if registry_resp.status == 200:
                        registry_data = await registry_resp.json()
                        # Check for version in image labels
                        if "images" in registry_data and registry_data["images"]:
                            first_image = registry_data["images"][0]
                            labels = first_image.get("labels", {})
                            for label in [
                                "org.opencontainers.image.version",
                                "version",
                                "VERSION",
                                "app.version",
                                "build.version"
                            ]:
                                if label in labels and labels[label]:
                                    version = labels[label]
                                    break
                        # If no version from labels, use tag or creation date
                        if not version:
                            if tag and tag != "latest":
                                version = tag
                            else:
                                if "images" in registry_data and registry_data["images"]:
                                    created = registry_data["images"][0].get("created", "")
                                    if created:
                                        try:
                                            from datetime import datetime
                                            dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                                            version = dt.strftime("%Y.%m.%d")
                                        except:
                                            version = "latest"
                                if not version:
                                    version = "latest"
                    else:
                        version = version or "latest"
            
            # Fallbacks
            if not version:
                version = "latest"
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
            
            # Cache
            if image_name in self._digest_cache:
                cached, ts = self._digest_cache[image_name]
                if (time.time() - ts) < self._cache_duration:
                    return cached

            digest = await self._get_remote_manifest_digest(image_name)
            if digest:
                short = (digest.split(":")[-1])[:12]
                self._digest_cache[image_name] = (short, time.time())
                return short
            
            # Fallback: Docker Hub API (digest in tag data)
            try:
                if not any(registry in image_name for registry in ["localhost:", "registry.", "harbor.", "gitlab.", "github.", "ghcr.io", "quay.io", "gcr.io", "azurecr.io", "ecr."]):
                    session = self.session or self.auth.session
                    if ":" in image_name:
                        tag = image_name.split(":")[-1]
                        repo = image_name.split(":")[0]
                    else:
                        tag = "latest"
                        repo = image_name
                    if repo.startswith("library/"):
                        clean_repo = repo.replace("library/", "")
                        registry_url = f"https://registry.hub.docker.com/v2/repositories/library/{clean_repo}/tags/{tag}"
                    elif "/" not in repo:
                        registry_url = f"https://registry.hub.docker.com/v2/repositories/library/{repo}/tags/{tag}"
                    else:
                        registry_url = f"https://registry.hub.docker.com/v2/repositories/{repo}/tags/{tag}"
                    _LOGGER.debug("🔍 Querying Docker Hub API: %s", registry_url)
                    async with session.get(registry_url, ssl=False) as registry_resp:
                        if registry_resp.status == 200:
                            registry_data = await registry_resp.json()
                            images_list = registry_data.get("images") or []
                            image_digest = None
                            if images_list and isinstance(images_list[0], dict):
                                image_digest = images_list[0].get("digest")
                            if not image_digest:
                                image_digest = registry_data.get("digest", "")
                            if image_digest:
                                short = (image_digest.split(":")[-1])[:12]
                                self._digest_cache[image_name] = (short, time.time())
                                return short
            except Exception as e:
                _LOGGER.debug("Docker Hub fallback failed for digest: %s", e)
            
            return "unknown"
                
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
