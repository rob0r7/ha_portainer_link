import logging
import aiohttp
import asyncio

_LOGGER = logging.getLogger(__name__)

class PortainerAPI:
    def __init__(self, host, username=None, password=None, api_key=None):
        self.host = host.rstrip("/")
        self.username = username
        self.password = password
        self.api_key = api_key
        self.jwt = None
        self.headers = {}

    async def initialize(self):
        if self.api_key:
            self.headers = {"X-API-Key": self.api_key}
        elif self.username and self.password:
            self.jwt = await self.authenticate()
            if self.jwt:
                self.headers = {"Authorization": f"Bearer {self.jwt}"}

    async def authenticate(self):
        url = f"{self.host}/api/auth"
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    url,
                    json={"Username": self.username, "Password": self.password},
                    ssl=False  # Disable SSL verification (self-signed certs)
                ) as resp:
                    resp.raise_for_status()
                    data = await resp.json()
                    return data.get("jwt")
        except Exception as e:
            _LOGGER.error("[PortainerAPI] Authentication failed: %s", e)
            return None

    async def get_containers(self, endpoint_id):
        url = f"{self.host}/api/endpoints/{endpoint_id}/docker/containers/json?all=1"
        try:
            async with aiohttp.ClientSession(headers=self.headers) as session:
                async with session.get(url, ssl=False) as resp:
                    resp.raise_for_status()
                    return await resp.json()
        except Exception as e:
            _LOGGER.error("[PortainerAPI] Failed to get containers: %s", e)
            return []

    async def start_container(self, endpoint_id, container_id):
        url = f"{self.host}/api/endpoints/{endpoint_id}/docker/containers/{container_id}/start"
        try:
            async with aiohttp.ClientSession(headers=self.headers) as session:
                async with session.post(url, ssl=False) as resp:
                    resp.raise_for_status()
                    return True
        except Exception as e:
            _LOGGER.error("[PortainerAPI] Failed to start container %s: %s", container_id, e)
            return False

    async def stop_container(self, endpoint_id, container_id):
        url = f"{self.host}/api/endpoints/{endpoint_id}/docker/containers/{container_id}/stop"
        try:
            async with aiohttp.ClientSession(headers=self.headers) as session:
                async with session.post(url, ssl=False) as resp:
                    resp.raise_for_status()
                    return True
        except Exception as e:
            _LOGGER.error("[PortainerAPI] Failed to stop container %s: %s", container_id, e)
            return False

    async def restart_container(self, endpoint_id, container_id):
        url = f"{self.host}/api/endpoints/{endpoint_id}/docker/containers/{container_id}/restart"
        try:
            async with aiohttp.ClientSession(headers=self.headers) as session:
                async with session.post(url, ssl=False) as resp:
                    resp.raise_for_status()
                    return True
        except Exception as e:
            _LOGGER.error("[PortainerAPI] Failed to restart container %s: %s", container_id, e)
            return False

    async def inspect_container(self, endpoint_id, container_id):
        url = f"{self.host}/api/endpoints/{endpoint_id}/docker/containers/{container_id}/json"
        try:
            async with aiohttp.ClientSession(headers=self.headers) as session:
                async with session.get(url, ssl=False) as resp:
                    resp.raise_for_status()
                    return await resp.json()
        except Exception as e:
            _LOGGER.error("[PortainerAPI] Failed to inspect container %s: %s", container_id, e)
            return None
