import logging
import aiohttp
from typing import List, Dict, Any, Optional
from aiohttp.client_exceptions import ClientConnectorCertificateError

_LOGGER = logging.getLogger(__name__)

class PortainerContainerAPI:
    """Handles all container-specific API operations."""

    def __init__(self, base_url: str, auth, ssl_verify: bool = True, session=None) -> None:
        self.base_url = base_url.rstrip("/")
        self.auth = auth
        self.ssl_verify = ssl_verify
        self.session = session  # Use shared session from main API

    async def _request(self, method: str, url: str, **kwargs) -> aiohttp.ClientResponse:
        kwargs.setdefault("ssl", self.ssl_verify)
        return await self.auth.request(method, url, **kwargs)

    async def _check_endpoint_exists_simple(self, endpoint_id: int) -> bool:
        url = f"{self.base_url}/api/endpoints/{endpoint_id}"
        async with await self._request("GET", url) as resp:
            if resp.status == 200:
                return True
            if resp.status == 404:
                _LOGGER.error("❌ Endpoint %s not found (404)", endpoint_id)
                return False
            _LOGGER.error("❌ Failed to check endpoint %s: HTTP %s", endpoint_id, resp.status)
            return False

    async def get_available_endpoints(self) -> List[Dict[str, Any]]:
        url = f"{self.base_url}/api/endpoints"
        async with await self._request("GET", url) as resp:
            if resp.status != 200:
                _LOGGER.error("❌ Could not list endpoints: HTTP %s", resp.status)
                return []
            return await resp.json()

    async def get_containers(self, endpoint_id: int) -> Optional[List[Dict[str, Any]]]:
        """Return containers or **None** on non-200 (so init can fail fast)."""
        url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/containers/json?all=1"
        _LOGGER.info("🔍 Getting containers from URL: %s", url)
        async with await self._request("GET", url) as resp:
            if resp.status == 200:
                containers = await resp.json()
                _LOGGER.info("✅ Got %d containers from endpoint %s", len(containers), endpoint_id)
                return containers
            if resp.status == 404:
                _LOGGER.error("❌ Endpoint %s not found (404)", endpoint_id)
                return None
            if resp.status == 403:
                _LOGGER.error("❌ Access denied (403) to endpoint %s", endpoint_id)
                return None
            _LOGGER.error("❌ Failed to get containers: HTTP %s", resp.status)
            return None

    async def inspect_container(self, endpoint_id: int, container_id: str) -> Optional[Dict[str, Any]]:
        url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/containers/{container_id}/json"
        async with await self._request("GET", url) as resp:
            if resp.status == 200:
                return await resp.json()
            _LOGGER.error("❌ Failed to inspect container %s: HTTP %s", container_id, resp.status)
            return None

    async def get_container_stats(self, endpoint_id: int, container_id: str) -> Optional[Dict[str, Any]]:
        url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/containers/{container_id}/stats?stream=false"
        async with await self._request("GET", url) as resp:
            if resp.status == 200:
                return await resp.json()
            _LOGGER.error("❌ Failed to get container stats: HTTP %s", resp.status)
            return None

    async def start_container(self, endpoint_id: int, container_id: str) -> bool:
        url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/containers/{container_id}/start"
        async with await self._request("POST", url) as resp:
            return resp.status == 204

    async def stop_container(self, endpoint_id: int, container_id: str) -> bool:
        url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/containers/{container_id}/stop"
        async with await self._request("POST", url) as resp:
            return resp.status == 204

    async def restart_container(self, endpoint_id: int, container_id: str) -> bool:
        url = f"{self.base_url}/api/endpoints/{endpoint_id}/docker/containers/{container_id}/restart"
        async with await self._request("POST", url) as resp:
            return resp.status == 204

    def get_container_stack_info(self, container_info: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        try:
            if not container_info:
                return {"stack_name": None, "service_name": None, "container_number": None, "is_stack_container": False}
            labels = container_info.get("Config", {}).get("Labels", {}) or {}
            stack_name = labels.get("com.docker.compose.project")
            service_name = labels.get("com.docker.compose.service")
            container_number = labels.get("com.docker.compose.container-number")
            if stack_name and service_name:
                return {"stack_name": stack_name, "service_name": service_name, "container_number": container_number, "is_stack_container": True}
            return {"stack_name": None, "service_name": None, "container_number": None, "is_stack_container": False}
        except Exception:
            return {"stack_name": None, "service_name": None, "container_number": None, "is_stack_container": False}

    async def check_endpoint_exists(self, endpoint_id: int) -> bool:
        """Check if a specific endpoint exists. TLS certificate errors are re-raised."""
        url = f"{self.base_url}/api/endpoints/{endpoint_id}"
        try:
            async with await self._request("GET", url) as resp:
                if resp.status == 200:
                    endpoint_data = await resp.json()
                    _LOGGER.debug("Endpoint %s exists: %s", endpoint_id, endpoint_data.get("Name", "Unknown"))
                    return True
                if resp.status == 404:
                    _LOGGER.error("❌ Endpoint %s does not exist (404)", endpoint_id)
                    return False
                _LOGGER.error("❌ Failed to check endpoint %s: HTTP %s", endpoint_id, resp.status)
                return False
        except ClientConnectorCertificateError:
            raise
        except Exception as e:
            _LOGGER.exception("❌ Error checking endpoint %s: %s", endpoint_id, e)
            return False
