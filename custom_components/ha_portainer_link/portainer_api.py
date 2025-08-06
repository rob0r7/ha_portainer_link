import logging
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
